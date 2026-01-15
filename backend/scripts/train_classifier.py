from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import tensorflow as tf


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a tiny query classifier on embedding vectors")
    parser.add_argument("--output", default="backend/models/doc_classifier.keras")
    parser.add_argument("--dim", type=int, default=384)
    parser.add_argument("--classes", type=int, default=4)
    args = parser.parse_args()

    # Placeholder synthetic data for MVP wiring. Replace with real labeled embeddings.
    samples = 400
    x = np.random.rand(samples, args.dim).astype(np.float32)
    y = tf.keras.utils.to_categorical(np.random.randint(0, args.classes, size=samples), num_classes=args.classes)

    model = tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=(args.dim,)),
            tf.keras.layers.Dense(128, activation="relu"),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(args.classes, activation="softmax"),
        ]
    )
    model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
    model.fit(x, y, epochs=4, batch_size=32, verbose=2)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    model.save(out)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
