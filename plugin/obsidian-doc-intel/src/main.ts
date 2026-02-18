import {
  App,
  ItemView,
  MarkdownRenderer,
  Notice,
  Plugin,
  PluginSettingTab,
  Setting,
  WorkspaceLeaf,
} from "obsidian";
import * as fsp from "fs/promises";
import * as os from "os";
import * as path from "path";

const VIEW_TYPE_DOC_INTEL = "doc-intel-chat-view";
const SKILL_SYNC_MARKER = ".managed_by_obsidianai";

type SkillSyncMode = "copy" | "symlink";
type SkillTarget = "codex" | "claude" | "both";

interface DocIntelSettings {
  backendUrl: string;
  topK: number;
  skillSourceFolderName: string;
  codexSkillsPath: string;
  claudeSkillsPath: string;
  skillSyncMode: SkillSyncMode;
}

interface SourceItem {
  file_path: string;
  score: number;
  title?: string;
  heading?: string;
  snippet: string;
  line_start?: number;
  line_end?: number;
}

interface QueryResponse {
  answer: string;
  sources: SourceItem[];
  confidence: number;
  route: string;
}

interface HistoryMessage {
  role: "user" | "assistant";
  text: string;
  sources?: SourceItem[];
  confidence?: number;
}

interface SkillEntry {
  name: string;
  fullPath: string;
  type: "directory" | "file";
}

interface SkillSyncResult {
  vaultPath: string;
  sourcePath: string;
  targets: Array<{ target: string; count: number; skills: string[] }>;
}

const DEFAULT_SETTINGS: DocIntelSettings = {
  backendUrl: "http://127.0.0.1:8000",
  topK: 6,
  skillSourceFolderName: "skills",
  codexSkillsPath: "~/.codex/skills/obsidian-vault",
  claudeSkillsPath: "~/.claude/skills/obsidian-vault",
  skillSyncMode: "copy",
};

export default class DocIntelPlugin extends Plugin {
  settings: DocIntelSettings = DEFAULT_SETTINGS;
  history: HistoryMessage[] = [];

  async onload() {
    await this.loadSettings();

    this.registerView(VIEW_TYPE_DOC_INTEL, (leaf) => new DocIntelView(leaf, this));

    this.addRibbonIcon("message-square", "Open Doc Intelligence", async () => {
      await this.activateView();
    });

    this.addCommand({
      id: "open-doc-intelligence",
      name: "Open Doc Intelligence",
      callback: async () => {
        await this.activateView();
      },
    });

    this.addCommand({
      id: "sync-vault-skills-both",
      name: "Sync Vault Skills To Codex + Claude",
      callback: async () => {
        await this.runSkillSync("both");
      },
    });

    this.addSettingTab(new DocIntelSettingTab(this.app, this));
    this.registerEvent(this.app.workspace.on("active-leaf-change", () => this.syncViewHistory()));
  }

  onunload() {
    this.app.workspace.getLeavesOfType(VIEW_TYPE_DOC_INTEL).forEach((leaf) => leaf.detach());
  }

  async loadSettings() {
    const saved = (await this.loadData()) || {};
    this.settings = { ...DEFAULT_SETTINGS, ...saved.settings };
    this.history = saved.history || [];
  }

  async saveSettings() {
    await this.saveData({ settings: this.settings, history: this.history.slice(-40) });
  }

  async activateView() {
    const { workspace } = this.app;
    let leaf = workspace.getLeavesOfType(VIEW_TYPE_DOC_INTEL)[0];

    if (!leaf) {
      leaf = workspace.getRightLeaf(false);
      if (!leaf) {
        new Notice("Unable to create side panel.");
        return;
      }
      await leaf.setViewState({ type: VIEW_TYPE_DOC_INTEL, active: true });
    }

    workspace.revealLeaf(leaf);
    this.syncViewHistory();
  }

  syncViewHistory() {
    this.app.workspace.getLeavesOfType(VIEW_TYPE_DOC_INTEL).forEach((leaf) => {
      const view = leaf.view;
      if (view instanceof DocIntelView) {
        view.renderHistory();
      }
    });
  }

  async runSkillSync(target: SkillTarget): Promise<SkillSyncResult> {
    const vaultBasePath = this.getVaultBasePath();
    if (!vaultBasePath) {
      throw new Error("Desktop vault path is unavailable. Skill sync works on desktop vaults only.");
    }

    const sourcePath = await this.detectSkillSourcePath(vaultBasePath);
    const skills = await this.collectSkills(sourcePath);
    if (skills.length === 0) {
      throw new Error(`No skills found in ${sourcePath}. Add SKILL.md folders or markdown files.`);
    }

    const targets =
      target === "both" ? ["codex", "claude"] : ([target] as Array<"codex" | "claude">);

    const targetResults: Array<{ target: string; count: number; skills: string[] }> = [];
    for (const t of targets) {
      const targetPath = this.resolveHomePath(
        t === "codex" ? this.settings.codexSkillsPath : this.settings.claudeSkillsPath
      );
      const result = await this.syncSkillsToTarget(skills, targetPath, this.settings.skillSyncMode);
      targetResults.push(result);
    }

    return {
      vaultPath: vaultBasePath,
      sourcePath,
      targets: targetResults,
    };
  }

  private getVaultBasePath(): string | null {
    const adapter = this.app.vault.adapter as { getBasePath?: () => string };
    if (typeof adapter.getBasePath !== "function") {
      return null;
    }
    return adapter.getBasePath();
  }

  private resolveHomePath(value: string): string {
    const input = value.trim();
    if (input.startsWith("~/")) {
      return path.join(os.homedir(), input.slice(2));
    }
    return path.resolve(input);
  }

  private async detectSkillSourcePath(vaultPath: string): Promise<string> {
    const vaultName = path.basename(vaultPath).toLowerCase();
    if (vaultName === "skill" || vaultName === "skills") {
      return vaultPath;
    }

    const sourcePref = this.settings.skillSourceFolderName.trim() || "skills";
    const candidates = Array.from(new Set([sourcePref, "skill", "skills"]));

    for (const name of candidates) {
      const full = path.join(vaultPath, name);
      if (await this.isDirectory(full)) {
        return full;
      }
    }

    throw new Error(
      `No skill source found. Checked vault root name and root folders: ${candidates.join(", "
      )}.`
    );
  }

  private async collectSkills(sourcePath: string): Promise<SkillEntry[]> {
    const children = await fsp.readdir(sourcePath, { withFileTypes: true });
    const skills: SkillEntry[] = [];

    for (const child of children) {
      if (child.name.startsWith(".")) continue;
      const full = path.join(sourcePath, child.name);

      if (child.isDirectory()) {
        const skillFile = path.join(full, "SKILL.md");
        if (await this.isFile(skillFile)) {
          skills.push({ name: child.name, fullPath: full, type: "directory" });
        }
        continue;
      }

      if (child.isFile() && child.name.toLowerCase().endsWith(".md")) {
        skills.push({ name: path.parse(child.name).name, fullPath: full, type: "file" });
      }
    }

    if (skills.length === 0 && (await this.isFile(path.join(sourcePath, "SKILL.md")))) {
      skills.push({ name: path.basename(sourcePath), fullPath: sourcePath, type: "directory" });
    }

    return skills.sort((a, b) => a.name.localeCompare(b.name));
  }

  private async syncSkillsToTarget(
    skills: SkillEntry[],
    targetPath: string,
    mode: SkillSyncMode
  ): Promise<{ target: string; count: number; skills: string[] }> {
    await this.prepareManagedTarget(targetPath);

    const created: string[] = [];
    for (const skill of skills) {
      const destination = path.join(targetPath, skill.name);
      if (mode === "symlink") {
        await this.linkSkill(skill, destination);
      } else {
        await this.copySkill(skill, destination);
      }
      created.push(skill.name);
    }

    return { target: targetPath, count: created.length, skills: created };
  }

  private async prepareManagedTarget(targetPath: string): Promise<void> {
    await fsp.mkdir(targetPath, { recursive: true });
    const markerPath = path.join(targetPath, SKILL_SYNC_MARKER);

    const entries = await fsp.readdir(targetPath);
    const hasMarker = entries.includes(SKILL_SYNC_MARKER);
    const nonMarker = entries.filter((entry) => entry !== SKILL_SYNC_MARKER);

    if (!hasMarker && nonMarker.length > 0) {
      throw new Error(
        `Target ${targetPath} contains unmanaged files. Use an empty folder or previously synced folder.`
      );
    }

    await Promise.all(nonMarker.map((entry) => fsp.rm(path.join(targetPath, entry), { recursive: true, force: true })));
    await fsp.writeFile(markerPath, "managed=true\n", "utf-8");
  }

  private async copySkill(skill: SkillEntry, destination: string): Promise<void> {
    if (skill.type === "directory") {
      await this.copyDirectoryRecursive(skill.fullPath, destination);
      return;
    }

    await fsp.mkdir(destination, { recursive: true });
    await fsp.copyFile(skill.fullPath, path.join(destination, "SKILL.md"));
  }

  private async linkSkill(skill: SkillEntry, destination: string): Promise<void> {
    if (skill.type === "directory") {
      await fsp.symlink(skill.fullPath, destination, "dir");
      return;
    }

    await fsp.mkdir(destination, { recursive: true });
    await fsp.symlink(skill.fullPath, path.join(destination, "SKILL.md"), "file");
  }

  private async copyDirectoryRecursive(sourceDir: string, destinationDir: string): Promise<void> {
    await fsp.mkdir(destinationDir, { recursive: true });
    const entries = await fsp.readdir(sourceDir, { withFileTypes: true });

    for (const entry of entries) {
      const src = path.join(sourceDir, entry.name);
      const dst = path.join(destinationDir, entry.name);
      if (entry.isDirectory()) {
        await this.copyDirectoryRecursive(src, dst);
      } else if (entry.isFile()) {
        await fsp.copyFile(src, dst);
      }
    }
  }

  private async isDirectory(candidate: string): Promise<boolean> {
    try {
      const stat = await fsp.stat(candidate);
      return stat.isDirectory();
    } catch {
      return false;
    }
  }

  private async isFile(candidate: string): Promise<boolean> {
    try {
      const stat = await fsp.stat(candidate);
      return stat.isFile();
    } catch {
      return false;
    }
  }
}

class DocIntelView extends ItemView {
  plugin: DocIntelPlugin;
  private chatContainer!: HTMLDivElement;
  private inputEl!: HTMLTextAreaElement;
  private sendBtn!: HTMLButtonElement;

  constructor(leaf: WorkspaceLeaf, plugin: DocIntelPlugin) {
    super(leaf);
    this.plugin = plugin;
  }

  getViewType() {
    return VIEW_TYPE_DOC_INTEL;
  }

  getDisplayText() {
    return "Doc Intelligence";
  }

  getIcon() {
    return "brain";
  }

  async onOpen() {
    this.contentEl.empty();
    this.contentEl.addClass("doc-intel-root");

    const header = this.contentEl.createDiv({ cls: "doc-intel-header" });
    header.createDiv({ text: "Document Intelligence", cls: "doc-intel-title" });

    this.chatContainer = this.contentEl.createDiv({ cls: "doc-intel-chat" });

    const composer = this.contentEl.createDiv({ cls: "doc-intel-composer" });
    this.inputEl = composer.createEl("textarea", {
      cls: "doc-intel-input",
      attr: { placeholder: "Ask about your notes...", rows: "3" },
    });
    this.sendBtn = composer.createEl("button", { text: "Send", cls: "doc-intel-send" });

    this.sendBtn.onclick = async () => this.handleSend();
    this.inputEl.onkeydown = async (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        await this.handleSend();
      }
    };

    this.renderHistory();
  }

  renderHistory() {
    if (!this.chatContainer) return;
    this.chatContainer.empty();

    this.plugin.history.forEach((msg) => {
      const bubble = this.chatContainer.createDiv({ cls: `doc-intel-msg ${msg.role}` });
      const body = bubble.createDiv({ cls: "doc-intel-msg-body" });
      MarkdownRenderer.renderMarkdown(msg.text, body, "", this.plugin);

      if (msg.role === "assistant") {
        const meta = bubble.createDiv({ cls: "doc-intel-meta" });
        if (msg.confidence !== undefined) {
          meta.setText(`Confidence ${(msg.confidence * 100).toFixed(0)}%`);
        }
        if (msg.sources && msg.sources.length > 0) {
          const srcWrap = bubble.createDiv({ cls: "doc-intel-sources" });
          msg.sources.forEach((s) => {
            const row = srcWrap.createDiv({ cls: "doc-intel-source-row" });
            const btn = row.createEl("button", {
              text: `${s.file_path}${s.heading ? `#${s.heading}` : ""}`,
              cls: "doc-intel-source-link",
            });
            btn.onclick = () => this.app.workspace.openLinkText(s.file_path, "", false);

            const preview = row.createDiv({ cls: "doc-intel-source-preview" });
            preview.setText(s.snippet);
          });
        }
      }
    });

    this.chatContainer.scrollTo({ top: this.chatContainer.scrollHeight, behavior: "smooth" });
  }

  private appendMessage(msg: HistoryMessage) {
    this.plugin.history.push(msg);
    if (this.plugin.history.length > 60) {
      this.plugin.history = this.plugin.history.slice(-60);
    }
    this.renderHistory();
    this.plugin.saveSettings();
  }

  private async handleSend() {
    const text = this.inputEl.value.trim();
    if (!text) return;

    this.appendMessage({ role: "user", text });
    this.inputEl.value = "";

    const loading = this.chatContainer.createDiv({ cls: "doc-intel-loading" });
    loading.setText("Thinking");

    try {
      this.sendBtn.disabled = true;
      const body = { query: text, top_k: this.plugin.settings.topK };
      const res = await fetch(`${this.plugin.settings.backendUrl}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        throw new Error(`Backend error ${res.status}`);
      }

      const data = (await res.json()) as QueryResponse;
      loading.remove();
      this.appendMessage({
        role: "assistant",
        text: `${data.answer}\n\n_Route: ${data.route}_`,
        sources: data.sources,
        confidence: data.confidence,
      });
    } catch (err) {
      loading.remove();
      const detail = err instanceof Error ? err.message : "Unknown failure";
      this.appendMessage({ role: "assistant", text: `Backend request failed: ${detail}` });
      new Notice(`Doc Intelligence error: ${detail}`);
    } finally {
      this.sendBtn.disabled = false;
    }
  }
}

class DocIntelSettingTab extends PluginSettingTab {
  plugin: DocIntelPlugin;

  constructor(app: App, plugin: DocIntelPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();

    containerEl.createEl("h2", { text: "Doc Intelligence Settings" });

    new Setting(containerEl)
      .setName("Backend URL")
      .setDesc("Local FastAPI backend URL")
      .addText((text) =>
        text
          .setPlaceholder("http://127.0.0.1:8000")
          .setValue(this.plugin.settings.backendUrl)
          .onChange(async (value) => {
            this.plugin.settings.backendUrl = value.trim();
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Top K")
      .setDesc("How many source chunks to retrieve")
      .addSlider((slider) =>
        slider
          .setLimits(1, 20, 1)
          .setDynamicTooltip()
          .setValue(this.plugin.settings.topK)
          .onChange(async (value) => {
            this.plugin.settings.topK = value;
            await this.plugin.saveSettings();
          })
      );

    containerEl.createEl("h3", { text: "Agent Skill Sync" });

    new Setting(containerEl)
      .setName("Skill source folder")
      .setDesc("Root folder inside vault for skill files/folders. If vault name is skill/skills, vault root is used.")
      .addText((text) =>
        text
          .setPlaceholder("skills")
          .setValue(this.plugin.settings.skillSourceFolderName)
          .onChange(async (value) => {
            this.plugin.settings.skillSourceFolderName = value.trim() || "skills";
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Sync mode")
      .setDesc("Copy is safest. Symlink keeps live references.")
      .addDropdown((dropdown) =>
        dropdown
          .addOption("copy", "Copy")
          .addOption("symlink", "Symlink")
          .setValue(this.plugin.settings.skillSyncMode)
          .onChange(async (value) => {
            this.plugin.settings.skillSyncMode = value as SkillSyncMode;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Codex skills path")
      .setDesc("Target path for Codex skills")
      .addText((text) =>
        text
          .setPlaceholder("~/.codex/skills/obsidian-vault")
          .setValue(this.plugin.settings.codexSkillsPath)
          .onChange(async (value) => {
            this.plugin.settings.codexSkillsPath = value.trim();
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Claude skills path")
      .setDesc("Target path for Claude Code skills")
      .addText((text) =>
        text
          .setPlaceholder("~/.claude/skills/obsidian-vault")
          .setValue(this.plugin.settings.claudeSkillsPath)
          .onChange(async (value) => {
            this.plugin.settings.claudeSkillsPath = value.trim();
            await this.plugin.saveSettings();
          })
      );

    const status = containerEl.createDiv();
    status.addClass("doc-intel-sync-status");
    status.setText("Ready to sync vault skills.");

    new Setting(containerEl)
      .setName("Sync skills now")
      .setDesc("Push vault skills into local coding agent skill directories")
      .addButton((btn) =>
        btn.setButtonText("Sync Codex").onClick(async () => {
          await this.handleSyncClick("codex", status);
        })
      )
      .addButton((btn) =>
        btn.setButtonText("Sync Claude").onClick(async () => {
          await this.handleSyncClick("claude", status);
        })
      )
      .addButton((btn) =>
        btn.setCta().setButtonText("Sync Both").onClick(async () => {
          await this.handleSyncClick("both", status);
        })
      );
  }

  private async handleSyncClick(target: SkillTarget, statusEl: HTMLDivElement): Promise<void> {
    statusEl.setText(`Syncing ${target}...`);
    try {
      const result = await this.plugin.runSkillSync(target);
      const targetSummary = result.targets.map((t) => `${t.target} (${t.count})`).join(" | ");
      statusEl.setText(`Synced ${result.targets.reduce((acc, t) => acc + t.count, 0)} skills from ${result.sourcePath}`);
      new Notice(`Skill sync complete: ${targetSummary}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Skill sync failed";
      statusEl.setText(message);
      new Notice(message);
    }
  }
}
