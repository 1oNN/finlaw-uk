# backend/data_preprocess.py
import json
from pathlib import Path
from datasets import load_dataset
from pdfminer.high_level import extract_text
from tqdm import tqdm

DATA_ROOT = Path(__file__).parent / "data"
OUT_PATH  = DATA_ROOT / "finetune.jsonl"
LEGIS_DIR = DATA_ROOT / "legislation" / "data"

def iter_legislation():
    ds = load_dataset(
        "parquet",
        data_files=[str(p) for p in LEGIS_DIR.glob("*.parquet")],
        split="train",
    )
    for ex in ds:
        yield {
            "text": ex["text"],
            "source": f"{ex.get('act','')}§{ex.get('section_id','')}",
            "type": "legislation"
        }

def iter_fca_pdfs():
    pdf_dir = DATA_ROOT / "fca"
    for pdf in pdf_dir.glob("*.pdf"):
        txt = extract_text(str(pdf))
        # basic paragraph splitting
        for para in txt.split("\n\n"):
            p = para.strip()
            if len(p) < 50:
                continue
            yield {
                "text": p,
                "source": pdf.name,
                "type": "fca_pdf"
            }

def iter_jsonl_slices():
    # if you have any .jsonl under data/
    for js in DATA_ROOT.rglob("*.jsonl"):
        if js.resolve() == OUT_PATH.resolve():
            continue
        for line in js.open("r", encoding="utf-8"):
            rec = json.loads(line)
            yield {
                "text": rec.get("text") or rec.get("answer",""),
                "source": js.name,
                "type": "slice"
            }

def main():
    # 1) remove old file
    if OUT_PATH.exists():
        OUT_PATH.unlink()
    DATA_ROOT.mkdir(exist_ok=True)

    # 2) open once, write fresh
    total = 0
    with OUT_PATH.open("w", encoding="utf-8") as out:
        for rec in tqdm(iter_legislation(), desc="Legislation"):
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            total += 1
        for rec in tqdm(iter_fca_pdfs(), desc="FCA PDFs"):
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            total += 1
        for rec in tqdm(iter_jsonl_slices(), desc="JSONL slices"):
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            total += 1

    print(f"✅  Wrote {total} records to {OUT_PATH}")

if __name__ == "__main__":
    main()
