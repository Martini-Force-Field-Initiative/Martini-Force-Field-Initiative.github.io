#!/usr/bin/env python3
import os
import yaml
from datetime import datetime
from pathlib import Path

def clean_string(value):
    """Clean a string value by stripping whitespace and quotes."""
    if isinstance(value, str):
        return value.strip().strip('"\'')
    return value

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
    # Path to the posts directory
    posts_dir = Path("docs/announcements/posts")
    
    # List to store all announcements
    announcements = []
    
    # Process each post directory
    for post_dir in posts_dir.iterdir():
        if post_dir.is_dir() and not post_dir.name.startswith('_'):
            # Look for the main Quarto file in the directory
            qmd_file = next(post_dir.glob("*.qmd"), None)
            if qmd_file:
                metadata = extract_metadata_from_file(qmd_file)
                if metadata:
                    # Extract required fields with defaults and clean strings
                    announcement = {
                        "title": clean_string(metadata.get("title", "Untitled")),
                        "description": clean_string(metadata.get("description", "")),
                        "date": clean_string(metadata.get("date", "")),
                        "image": get_image_path(metadata.get("image", ""), post_dir.name),
                        "url": generate_url(post_dir.name),
                        "author": clean_string(metadata.get("author", "Unknown Author"))
                    }
                    announcements.append(announcement)
    
    # Sort announcements by date (newest first)
    announcements.sort(key=lambda x: datetime.strptime(x["date"], "%m/%d/%Y"), reverse=True)
    
    # Take only the three latest announcements
    latest_announcements = announcements[:3]
    
    # Create the metadata structure
    metadata = {
        "title-block-banner": "#EDF3F9",
        "title-block-banner-color": "body",
        "search": False,
        "announcements": latest_announcements
    }
    
    # Write the metadata to a YAML file
    output_file = posts_dir / "_metadata.yml"
    with open(output_file, 'w', encoding='utf-8') as f:
        # Custom YAML dumper to add newlines between announcements
        class CustomDumper(yaml.Dumper):
            def increase_indent(self, flow=False, indentless=False):
                return super().increase_indent(flow, indentless)
            
            def represent_list(self, data):
                # Add newline before each item in the list
                return super().represent_list(data)
            
            def represent_str(self, data):
                # Remove quotes from strings
                return self.represent_scalar('tag:yaml.org,2002:str', data, style='')
        
        # Register the custom representer
        CustomDumper.add_representer(list, CustomDumper.represent_list)
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