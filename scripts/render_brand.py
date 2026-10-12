"""Render original OVAPI transit-sign artwork; no downloaded icons or fonts."""

from pathlib import Path

from PIL import Image, ImageDraw

BRAND = Path("custom_components/ovapi/brand")
INK = "#102F40"
PAPER = "#F4FAFC"
AMBER = "#FFC04A"
SCALE = 4


def symbol(dark: bool) -> Image.Image:
    image = Image.new("RGBA", (256 * SCALE, 256 * SCALE))
    draw = ImageDraw.Draw(image)
    foreground, background = (PAPER, INK) if dark else (INK, PAPER)

    def box(bounds: tuple[int, int, int, int], color: str, radius: int = 0) -> None:
        draw.rounded_rectangle(
            tuple(value * SCALE for value in bounds),
            radius=radius * SCALE,
            fill=color,
        )

    box((8, 8, 248, 212), foreground, 32)
    box((20, 20, 236, 200), background, 22)
    box((32, 34, 224, 74), foreground, 10)
    for y, width in ((94, 210), (130, 190), (166, 210)):
        box((34, y, 58, y + 20), INK, 5)
        box((38, y + 4, 54, y + 16), AMBER, 2)
        box((76, y + 5, width, y + 15), foreground, 5)
    box((66, 212, 82, 248), foreground, 4)
    box((174, 212, 190, 248), foreground, 4)
    return image


def logo(dark: bool) -> Image.Image:
    image = Image.new("RGBA", (896 * SCALE, 256 * SCALE))
    image.alpha_composite(symbol(dark))
    draw = ImageDraw.Draw(image)
    color = PAPER if dark else INK
    # Original monoline letterforms, independent of installed system fonts.
    letters = (
        (
            (0, 20),
            (0, 100),
            (16, 116),
            (64, 116),
            (80, 100),
            (80, 20),
            (64, 4),
            (16, 4),
            (0, 20),
        ),
        ((0, 4), (40, 116), (80, 4)),
        ((0, 116), (40, 4), (80, 116)),
        ((0, 116), (0, 4), (60, 4), (80, 24), (80, 50), (60, 70), (0, 70)),
        ((24, 4), (24, 116)),
    )
    for index, points in enumerate(letters):
        x = 296 + index * 124
        draw.line(
            [((x + px) * SCALE, (68 + py) * SCALE) for px, py in points],
            fill=color,
            width=14 * SCALE,
            joint="curve",
        )
        if index == 2:
            draw.line(
                ((x + 17) * SCALE, 144 * SCALE, (x + 63) * SCALE, 144 * SCALE),
                fill=color,
                width=14 * SCALE,
            )
    return image


def main() -> None:
    BRAND.mkdir(exist_ok=True)
    for dark in (False, True):
        for kind, source in (("icon", symbol(dark)), ("logo", logo(dark))):
            for factor in (1, 2):
                width, height = source.size
                name = (
                    f"{'dark_' if dark else ''}{kind}{'@2x' if factor == 2 else ''}.png"
                )
                source.resize(
                    (width * factor // SCALE, height * factor // SCALE),
                    Image.Resampling.LANCZOS,
                ).save(BRAND / name, optimize=True)


if __name__ == "__main__":
    main()
