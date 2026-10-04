import os
import gdown

def download_model_checkpoint(gdrive_file_id, output_path):
    """
    Download model checkpoint from Google Drive if it doesn't exist.
    
    Args:
        gdrive_file_id (str): Google Drive file ID
        output_path (str): Path where model will be saved
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Check if file already exists
    if not os.path.exists(output_path):
        print(f"Downloading model checkpoint to {output_path}...")
        url = f'https://drive.google.com/uc?id={gdrive_file_id}'
        try:
            downloaded_path = gdown.download(url, output_path, quiet=False)
        except Exception as exc:
            raise RuntimeError(
                "Skin-lesion checkpoint download failed. Check network access "
                f"and write permissions for {output_path}: {exc}"
            ) from exc
        if downloaded_path is None or not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError(
                "Skin-lesion checkpoint download failed. Google Drive returned no "
                f"usable file for {output_path}; check network access and retry."
            )
        print("Download complete!")

# Usage in app.py
# download_model_checkpoint('your_gdrive_file_id', 'path/to/checkpoint.pth')
