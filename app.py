from flask import Flask, render_template, request, url_for
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter
import io
import os

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    label_url = None
    if request.method == 'POST':
        data = {k: request.form[k] for k in request.form}
        CODE128 = barcode.get_barcode_class('code128')
        barcode_writer = ImageWriter()
        barcode_writer.set_options({'write_text': False})
        barcode_img = CODE128(data['barcode_number'], writer=barcode_writer).render()

        # Try to load Times font, fallback to DejaVuSans if not available
        try:
            font_regular = ImageFont.truetype("fonts/times.ttf", 16)
            font_bold = ImageFont.truetype("fonts/timesbd.ttf", 16)
            font_small = ImageFont.truetype("fonts/times.ttf", 13)
        except OSError:
            font_regular = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
            font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)

        def get_text_size(text, font):
            bbox = font.getbbox(text)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]

        def draw_centered_multiline(lines, box, font):
            if isinstance(lines, str):
                lines = lines.split('\n')
            line_height = int(get_text_size('A', font)[1] * 1.7)  # Try 1.7 or 2.0
            total_height = line_height * len(lines)
            y = box[1] + (box[3] - box[1] - total_height) / 2
            for line in lines:
                w, _ = get_text_size(line, font)
                x = box[0] + (box[2] - box[0] - w) / 2
                draw.text((x, y), line, font=font, fill='black')
                y += line_height

        def wrap_multiline_text(text, font, max_width):
            wrapped = []
            for line in text.split('\n'):
                if not line.strip():
                    wrapped.append('')
                    continue
                words = line.split()
                current = words[0]
                for word in words[1:]:
                    test = current + ' ' + word
                    w, _ = get_text_size(test, font)
                    if w <= max_width:
                        current = test
                    else:
                        wrapped.append(current)
                        current = word
                wrapped.append(current)
            return wrapped

        def draw_centered_header(text, box, font):
            # If text is too wide, reduce font size or wrap
            w, _ = get_text_size(text, font)
            max_width = box[2] - box[0] - 4  # 4px padding
            if w > max_width:
                # Try wrapping
                import textwrap
                lines = textwrap.wrap(text, width=18)  # Adjust width as needed
                draw_centered_multiline(lines, box, font)
            else:
                draw_centered_multiline(text, box, font)

        # Image setup
        img_width = 400
        cell_pad_x = 8
        cell_pad_y = 6

        col_width = (img_width // 2) - 2 * cell_pad_x

        # Customer Address
        address_text_main = f"{data['customer_name']}\n{data['customer_address']}"
        address_lines = wrap_multiline_text(address_text_main, font_regular, col_width)
        pincode_text = data['pincode']

        # Return Address
        return_text = f"{data['return_address']}\n{data['return_pincode']}"
        return_lines = wrap_multiline_text(return_text, font_regular, col_width)

        # Line Heights
        line_height_regular = int(get_text_size('A', font_regular)[1] * 1.3)
        line_height_bold = int(get_text_size('A', font_bold)[1] * 1.3)
        line_height_small = int(get_text_size('A', font_small)[1] * 1.3)
        header_height = line_height_bold + 2 * cell_pad_y

        # Top box height dynamically
        total_address_height = len(address_lines) * line_height_regular + line_height_small + 2 * cell_pad_y + 4
        return_height = len(return_lines) * line_height_regular + 2 * cell_pad_y
        top_box_height = max(header_height + total_address_height, header_height + return_height)

        # Barcode section
        barcode_height = 60
        barcode_num_height = get_text_size(data['barcode_number'], font_bold)[1]
        barcode_section_height = barcode_height + barcode_num_height + 20

        # Bottom section height dynamically
        amount_text = str(data['amount'])
        hub_text = data['destination_hub']
        amount_lines = wrap_multiline_text(amount_text, font_regular, col_width)
        hub_lines = wrap_multiline_text(hub_text, font_regular, col_width)
        bottom_lines = max(len(amount_lines), len(hub_lines))
        bottom_box_height = header_height + bottom_lines * line_height_regular + 2 * cell_pad_y

        # Total image height
        img_height = int(top_box_height + barcode_section_height + bottom_box_height)
        img = Image.new('RGB', (img_width, img_height), 'white')
        draw = ImageDraw.Draw(img)

        # Draw section boxes
        draw.rectangle([0, 0, img_width//2, top_box_height], outline='black', width=2)
        draw.rectangle([img_width//2, 0, img_width, top_box_height], outline='black', width=2)
        draw.rectangle([0, top_box_height, img_width, top_box_height + barcode_section_height], outline='black', width=2)
        draw.rectangle([0, top_box_height + barcode_section_height, img_width//2, img_height], outline='black', width=2)
        draw.rectangle([img_width//2, top_box_height + barcode_section_height, img_width, img_height], outline='black', width=2)

        # Section headers
        draw_centered_header("Customer Address", [0, 0, img_width//2, header_height], font_bold)
        draw_centered_header("If Undelivered, Return to", [img_width//2, 0, img_width, header_height], font_bold)

        # Draw customer address lines
        y = header_height + cell_pad_y
        for line in address_lines:
            draw.text((cell_pad_x, y), line, font=font_regular, fill='black')
            y += line_height_regular
        y += 4  # space before pincode
        draw.text((cell_pad_x, y), pincode_text, font=font_regular, fill='black')  # use font_regular, not font_small

        # Draw return address
        y = header_height + cell_pad_y
        for line in return_lines:
            draw.text((img_width//2 + cell_pad_x, y), line, font=font_regular, fill='black')
            y += line_height_regular

        # Draw barcode
        barcode_w = img_width - 40
        barcode_x = 20
        barcode_y = top_box_height + 5
        img.paste(barcode_img.resize((barcode_w, barcode_height)), (barcode_x, barcode_y))

        # Bottom left: Amount
        draw_centered_header("Amount to be collected", [0, top_box_height + barcode_section_height, img_width//2, top_box_height + barcode_section_height + header_height], font_bold)
        draw_centered_multiline(amount_text, [0, top_box_height + barcode_section_height + header_height, img_width//2, img_height], font_regular)

        # Bottom right: Destination Hub
        draw_centered_header("Destination Hub", [img_width//2, top_box_height + barcode_section_height, img_width, top_box_height + barcode_section_height + header_height], font_bold)
        draw_centered_multiline(hub_text, [img_width//2, top_box_height + barcode_section_height + header_height, img_width, img_height], font_regular)

        # Save to buffer
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        label_path = os.path.join('static', 'shipping_label.png')
        with open(label_path, 'wb') as f:
            f.write(buf.getbuffer())
        label_url = url_for('static', filename='shipping_label.png')

    return render_template('form.html', label_url=label_url)

if __name__ == '__main__':
    if not os.path.exists('static'):
        os.makedirs('static')
    app.run(debug=True)
