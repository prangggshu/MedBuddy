"""Generate a SYNTHETIC prescription image for demos (fake doctor, fake patient).

    python -m scripts.make_demo_rx

Writes data/sample_prescriptions/demo_rx.jpg. The drugs are chosen to exercise every
MedBuddy feature from the curated datasets:
  Warf + Ecosprin    -> major interaction (warfarin + aspirin)
  Ecosprin + Brufen  -> moderate interaction (aspirin + ibuprofen)
  Crocin             -> recognised brand, no interaction
  Zentrovax          -> made-up drug -> "not in MedBuddy's dataset" path

Needs Pillow (dev-only: pip install pillow). Uses Windows fonts, falls back to default.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "data" / "sample_prescriptions" / "demo_rx.jpg"
FONTS = Path("C:/Windows/Fonts")

INK = (25, 35, 80)
ACCENT = (20, 90, 140)
GREY = (110, 110, 110)

MEDICINES = [
    ("Tab. Warf 5 mg", "1 tablet once daily at night", "30 days"),
    ("Tab. Ecosprin 75 mg", "1 tablet once daily after lunch", "30 days"),
    ("Tab. Brufen 400 mg", "1 tablet twice daily after food", "5 days"),
    ("Tab. Crocin 650 mg", "1 tablet when needed for fever (max 3/day)", "5 days"),
    ("Cap. Zentrovax 10 mg", "1 capsule once daily before breakfast", "14 days"),
]


def _font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(FONTS / name), size)
    except OSError:
        return ImageFont.load_default(size=size)


def main() -> None:
    w, h = 1240, 1650
    img = Image.new("RGB", (w, h), (252, 251, 246))
    d = ImageDraw.Draw(img)

    title, bold, body, small = (
        _font("georgiab.ttf", 46),
        _font("arialbd.ttf", 30),
        _font("arial.ttf", 28),
        _font("arial.ttf", 22),
    )

    # Header
    d.text((70, 60), "Dr. Meera Kapoor", font=title, fill=ACCENT)
    d.text((70, 120), "MBBS, MD (General Medicine)  ·  Reg. No. DEMO-0000", font=small, fill=GREY)
    d.text((70, 150), "Sunrise Demo Clinic, 12 Example Road, Bhubaneswar", font=small, fill=GREY)
    d.line((70, 195, w - 70, 195), fill=ACCENT, width=4)

    # Patient
    d.text((70, 225), "Patient: Asha Verma (SYNTHETIC)", font=body, fill=INK)
    d.text((70, 265), "Age/Sex: 60 / F", font=body, fill=INK)
    d.text((w - 380, 225), "Date: 09-10-2026", font=body, fill=INK)
    d.text((70, 305), "Diagnosis: Atrial fibrillation, knee pain, fever", font=body, fill=INK)

    # Rx
    d.text((70, 375), "Rx", font=_font("georgiab.ttf", 64), fill=ACCENT)
    y = 470
    for i, (name, freq, dur) in enumerate(MEDICINES, 1):
        d.text((110, y), f"{i}.  {name}", font=bold, fill=INK)
        d.text((165, y + 42), f"{freq}  —  {dur}", font=body, fill=INK)
        y += 125

    # Advice + signature
    d.text((70, y + 20), "Advice: Review INR after 1 week. Avoid alcohol.", font=body, fill=INK)
    d.text((w - 420, y + 140), "Dr. Meera Kapoor", font=_font("segoesc.ttf", 38), fill=INK)
    d.line((w - 430, y + 195, w - 90, y + 195), fill=GREY, width=2)
    d.text((w - 330, y + 205), "Signature", font=small, fill=GREY)

    # Synthetic notice
    d.line((70, h - 120, w - 70, h - 120), fill=ACCENT, width=2)
    d.text(
        (70, h - 95),
        "SYNTHETIC PRESCRIPTION — generated for MedBuddy demo. Not a real patient or doctor.",
        font=small,
        fill=GREY,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "JPEG", quality=92)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
