# app/utils/photos.py -- violation/ticket photo upload helper (spec section 7).
# CS50x map: CS50x never took uploads. Pillow shrinks to max 1280px so phone
# photos don't blow up the disk/DB. Stored under app/static/uploads/ (gitignored).
import os  # build the upload path
import uuid  # unique filenames (no collisions when two SAs upload at once)
from flask import current_app  # locate app/static at runtime
from werkzeug.utils import secure_filename  # strip path tricks from the client filename
from PIL import Image  # Pillow: open + thumbnail + save

#: Long side capped at 1280px (spec section 7). JPEG quality keeps files small.
MAX_SIDE = 1280
JPEG_QUALITY = 82
#: Accepted extensions (checked by name AND by Pillow actually opening the file).
ALLOWED_EXTS = {"jpg", "jpeg", "png", "webp"}


def save_violation_photo(file_storage):
    """Shrink + save an uploaded photo. Returns the RELATIVE path for photo_path.

    Returns None when no file was uploaded. Raises ValueError on bad files
    (route flashes the message, nothing commits). Saved as JPEG
    uploads/violations/<uuid>.jpg, long side <= 1280px.
    """
    if file_storage is None:
        return None
    filename = (getattr(file_storage, "filename", "") or "").strip()
    if not filename:
        return None  # empty file input = no photo, not an error
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    _ = secure_filename(filename)  # validate it sanitizes (uuid is the stored name)
    if ext not in ALLOWED_EXTS:
        raise ValueError("Photo must be JPG, PNG or WebP.")
    upload_dir = os.path.join(current_app.static_folder, "uploads", "violations")
    os.makedirs(upload_dir, exist_ok=True)
    try:
        img = Image.open(file_storage.stream)
        img.verify()  # proves it is really an image (catches renamed .exe etc.)
        file_storage.stream.seek(0)
        img = Image.open(file_storage.stream).convert("RGB")  # JPEG needs RGB
    except Exception:
        raise ValueError("That file is not a readable photo.")
    img.thumbnail((MAX_SIDE, MAX_SIDE))  # keeps aspect ratio, shrinks only if bigger
    name = "v_%s.jpg" % uuid.uuid4().hex
    img.save(os.path.join(upload_dir, name), "JPEG", quality=JPEG_QUALITY, optimize=True)
    return "uploads/violations/" + name
