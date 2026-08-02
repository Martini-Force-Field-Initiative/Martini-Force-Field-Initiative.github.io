#!/usr/bin/env python3
import os
import yaml
from datetime import datetime
from pathlib import Path

DATE_FORMAT = "%m/%d/%Y"

def clean_string(value):
    """Clean a string value by stripping whitespace and quotes."""
    if isinstance(value, str):
        return value.strip().strip('"\'')
    return value

def parse_date(value):
    """Parse a front matter date, returning None if it is missing or malformed."""
    try:
        return datetime.strptime(value, DATE_FORMAT)
    except (TypeError, ValueError):
        return None

def extract_metadata_from_file(file_path):
    """Extract metadata from a Quarto markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split the content to get the YAML front matter
    parts = content.split('---', 2)
    if len(parts) < 3:
        return None
    
    try:
        metadata = yaml.safe_load(parts[1])
        # Clean all string values in the metadata
        if metadata:
            metadata = {k: clean_string(v) for k, v in metadata.items()}
        return metadata
    except yaml.YAMLError:
        return None

def generate_url(post_dir):
    """Generate the URL for a post."""
    return f"/docs/announcements/posts/{post_dir}/"

def get_image_path(image_value, post_dir):
    """Get the image path, using default if empty or prepending post directory if specified."""
    cleaned_image = clean_string(image_value)
    if not cleaned_image:
        return "/images/cell1.jpg"
    # If image path is specified, prepend the post directory
    return f"/docs/announcements/posts/{post_dir}/{cleaned_image}"

def main():
    # Paths resolved relative to this script 
    repo_root = Path(__file__).resolve().parent.parent
    posts_dir = repo_root / "docs" / "announcements" / "posts"

    # List to store all announcements
    announcements = []
    # Front matter problems worth failing on, rather than silently skipping
    errors = []

    # Process each post directory (sorted, so equal dates break ties consistently)
    for post_dir in sorted(posts_dir.iterdir()):
        if post_dir.is_dir() and not post_dir.name.startswith('_'):
            # Look for the main Quarto file in the directory
            qmd_file = next(post_dir.glob("*.qmd"), None)
            if qmd_file:
                metadata = extract_metadata_from_file(qmd_file)
                if metadata:
                    date_value = clean_string(metadata.get("date", ""))
                    if parse_date(date_value) is None:
                        errors.append(f"{qmd_file.relative_to(repo_root)}: invalid date {date_value!r}")
                        continue
                    # Extract required fields with defaults and clean strings
                    announcement = {
                        "title": clean_string(metadata.get("title", "Untitled")),
                        "description": clean_string(metadata.get("description", "")),
                        "date": date_value,
                        "image": get_image_path(metadata.get("image", ""), post_dir.name),
                        "url": generate_url(post_dir.name),
                        "author": clean_string(metadata.get("author", "Unknown Author"))
                    }
                    announcements.append(announcement)

    # Report every bad post at once, so a contributor fixes them in one pass
    if errors:
        raise SystemExit(
            "Invalid announcement front matter:\n"
            + "\n".join(f"  {error}" for error in errors)
            + "\n\nDates must use MM/DD/YYYY (e.g. \"02/12/2026\")."
        )

    # Sort announcements by date (newest first); every date parsed above
    announcements.sort(key=lambda x: parse_date(x["date"]) or datetime.min, reverse=True)
    
    # Take only the three latest announcements
    latest_announcements = announcements[:4]
    
    # Create the metadata structure
    metadata = {
        "title-block-banner": "#FDF7F4",
        "title-block-banner-color": "body",
        "search": False,
        "announcements": latest_announcements
    }
    
    # Write the metadata to a YAML file
    output_file = posts_dir / "_metadata.yml"
    with open(output_file, 'w', encoding='utf-8') as f:
        # Custom YAML dumper to double quote every value
        class CustomDumper(yaml.Dumper):
            def represent_str(self, data):
                # Double quotes: news-loader.js strips " when parsing this file
                return self.represent_scalar('tag:yaml.org,2002:str', data, style='"')

            def represent_mapping(self, tag, mapping, flow_style=None):
                node = super().represent_mapping(tag, mapping, flow_style)
                for key_node, _ in node.value:
                    key_node.style = None  # keys stay unquoted
                return node

        # Register the custom representer
        CustomDumper.add_representer(str, CustomDumper.represent_str)
        
        # Dump with custom settings
        yaml.dump(
            metadata,
            f,
            Dumper=CustomDumper,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=1000,  # Prevent line wrapping
            indent=2,    # Consistent indentation
            default_style=None  # Use block style for better readability
        )

if __name__ == "__main__":
    main() 