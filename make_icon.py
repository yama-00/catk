from PIL import Image, ImageDraw

sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
base = Image.new("RGBA", (512, 512), (34, 45, 67, 255))  # 濃紺の背景
draw = ImageDraw.Draw(base)
draw.ellipse((64, 64, 448, 448), fill=(80, 180, 255, 255))  # 水色の円
base.save("src/catk/resources/icon.ico", sizes=sizes)

print("OK: src/catk/resources/icon.ico を作成しました")
