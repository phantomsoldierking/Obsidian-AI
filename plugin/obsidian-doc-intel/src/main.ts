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

const VIEW_TYPE_DOC_INTEL = "doc-intel-chat-view";

interface DocIntelSettings {
  backendUrl: string;
  topK: number;
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

const DEFAULT_SETTINGS: DocIntelSettings = {
  backendUrl: "http://127.0.0.1:8000",
  topK: 6,
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
  }
}
