import os
import glob
from pathlib import Path
import nbformat
from nbconvert import HTMLExporter
from pygments import highlight
from pygments.lexers import get_lexer_for_filename
from pygments.formatters import HtmlFormatter

# Target directory
TARGET_DIR = r"C:\Users\venub\Desktop\Projects\AMD hackathon\Aria-gui\AMD-ROCKIT\elyra_work\HF_Space_hipVS"

def convert_notebook_to_html(file_path):
    print(f"Converting Notebook: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            nb = nbformat.read(f, as_version=4)
        html_exporter = HTMLExporter()
        html_exporter.template_name = 'classic'
        (body, resources) = html_exporter.from_notebook_node(nb)
        
        output_path = file_path.with_suffix('.html')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(body)
        return True
    except Exception as e:
        print(f"Error converting {file_path}: {e}")
        return False

def convert_code_to_html(file_path):
    print(f"Converting Code/Text: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
            
        lexer = get_lexer_for_filename(file_path.name, stripall=True)
        formatter = HtmlFormatter(linenos=True, full=True, style='monokai')
        html_content = highlight(code, lexer, formatter)
        
        output_path = file_path.with_suffix('.html')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return True
    except Exception as e:
        print(f"Error converting {file_path}: {e}")
        return False

def main():
    target_path = Path(TARGET_DIR)
    if not target_path.exists():
        print(f"Directory not found: {TARGET_DIR}")
        return

    # Find all target files
    extensions = ['.py', '.md', '.txt', '.json', '.ipynb']
    files_to_convert = []
    
    for ext in extensions:
        files_to_convert.extend(target_path.rglob(f"*{ext}"))

    for file_path in files_to_convert:
        if file_path.name == "convert_to_html.py":
            continue # skip the script itself if it's in there
            
        success = False
        if file_path.suffix == '.ipynb':
            success = convert_notebook_to_html(file_path)
        else:
            success = convert_code_to_html(file_path)
            
        if success:
            print(f"Success! Deleting original: {file_path.name}")
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Could not delete {file_path}: {e}")

if __name__ == "__main__":
    main()
