from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "lifechoice-demo.mp4"
SIZE = (1280, 720)
FPS = 12


def font(size: int, bold: bool = False):
    names = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def title_card(title: str, subtitle: str) -> Image.Image:
    image = Image.new("RGB", SIZE, "#080812")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((80, 90, 1200, 630), radius=32, fill="#141128", outline="#7568ff", width=3)
    draw.text((130, 155), "BUILD SMALL HACKATHON", fill="#a99fff", font=font(24, True))
    draw.text((130, 245), title, fill="white", font=font(62, True))
    draw.multiline_text((130, 350), subtitle, fill="#d3cee7", font=font(30), spacing=12)
    return image


def screenshot_card(filename: str, heading: str, caption: str, crop_top: int = 0) -> Image.Image:
    source = Image.open(ROOT / "screenshots" / filename).convert("RGB")
    source = source.crop((0, crop_top, source.width, min(source.height, crop_top + int(source.width * 0.56))))
    source.thumbnail((1120, 540), Image.Resampling.LANCZOS)
    image = Image.new("RGB", SIZE, "#080812")
    draw = ImageDraw.Draw(image)
    draw.text((70, 34), heading, fill="white", font=font(34, True))
    x = (SIZE[0] - source.width) // 2
    image.paste(source, (x, 100))
    draw.rounded_rectangle((60, 640, 1220, 700), radius=16, fill="#18152e")
    draw.text((90, 656), caption, fill="#eeeaff", font=font(22))
    return image


def write_frames(writer, image: Image.Image, seconds: float) -> None:
    frame = np.asarray(image)
    for _ in range(round(FPS * seconds)):
        writer.append_data(frame)


def main() -> None:
    cards = [
        (title_card("LifeChoice Simulator", "A causal decision simulator, not another chatbot.\nQwen2.5-7B + Gradio + deterministic state."), 3.0),
        (screenshot_card("onboarding.png", "Start in seconds", "One concrete calibration answer takes you directly into the simulation."), 4.0),
        (screenshot_card("simulation.png", "Immediate first scene", "The opening is deterministic; later nodes prefetch in the background."), 4.0),
        (screenshot_card("cascade.png", "Choices return later", "Facts, obligations, and closed options make branches materially different.", 500), 4.0),
        (screenshot_card("report.png", "A report grounded in behavior", "Five metrics, three cascade moments, and a bounded causal ledger.", 500), 4.0),
        (title_card("Small model. Real state.", "7.616B parameters. No 32B+ fallback.\nBuilt with Codex for the Build Small Hackathon."), 3.0),
    ]
    with imageio.get_writer(
        OUT,
        fps=FPS,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
        macro_block_size=1,
    ) as writer:
        for card, seconds in cards:
            write_frames(writer, card, seconds)
    print(OUT)


if __name__ == "__main__":
    main()
