#!/usr/bin/env python3
# backend/train_tinyllama.py
# Fine-tune TinyLlama-1.1B-Chat locally (FP16 + LoRA on Windows).

import os
import torch
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    Trainer,
    TrainingArguments,
)
from peft import get_peft_model, LoraConfig

# ── CONFIG ────────────────────────────────────────────────────────────────

# Fix: point to the local model folder
MODEL_PATH = r"C:\Users\hamma\Desktop\FYP\tinyllama-chat-app\backend\models\TinyLlama-1.1B-Chat-v1.0"

# Fix: use relative path from this script to data/finetune.jsonl
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "finetune.jsonl")

# Output adapter directory
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "models", "tinyllama-legal-lora")

# Hyperparameters
BATCH_SIZE     = 4
GRAD_ACC_STEPS = 8
LR             = 2e-4
EPOCHS         = 3
MAX_SEQ_LEN    = 512

# ── MODEL & TOKENIZER ───────────────────────────────────────────────────────

print(f"Loading tokenizer & model from {MODEL_PATH}")
tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    local_files_only=True,
    trust_remote_code=True
)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    device_map="auto",
    torch_dtype=torch.float16,
    local_files_only=True,
    trust_remote_code=True
)

# ── APPLY LoRA ─────────────────────────────────────────────────────────────

print("Applying LoRA adapter")
lora_config = LoraConfig(
    task_type="CAUSAL_LM",
    r=8,
    lora_alpha=16,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none",
)
model = get_peft_model(model, lora_config)

# ── DATASET & TOKENIZATION ─────────────────────────────────────────────────

print(f"Loading dataset from {DATA_FILE}")
dataset = load_dataset("json", data_files=DATA_FILE, split="train")

def tokenize_fn(ex):
    text = ex.get("instruction", ex.get("text", ""))
    if "response" in ex:
        # Combine instruction + response for causal LM
        inp = text + "\n" + ex["response"]
    else:
        inp = text
    enc = tokenizer(
        inp,
        truncation=True,
        max_length=MAX_SEQ_LEN,
        padding="max_length",
    )
    # For simple finetuning, use input_ids as labels (causal LM)
    enc["labels"] = enc["input_ids"].copy()
    return enc

print("Tokenizing dataset…")
tokenized = dataset.map(
    tokenize_fn,
    batched=False,
    remove_columns=dataset.column_names,
)

# ── TRAINING SETUP ──────────────────────────────────────────────────────────

training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRAD_ACC_STEPS,
    learning_rate=LR,
    num_train_epochs=EPOCHS,
    fp16=True,
    logging_steps=50,
    save_steps=200,
    save_total_limit=2,
    report_to="none",
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized,
    tokenizer=tokenizer,
)

# ── RUN TRAINING ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting training…")
    trainer.train()
    print(f"Saving adapter to {OUTPUT_DIR}")
    model.save_pretrained(OUTPUT_DIR)
    print("✅ Done.")
