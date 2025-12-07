#!/usr/bin/env python3
"""
Docker-based spaCy extractor that runs spaCy in a container.
Bypasses local ARM64/Python compatibility issues.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import List

logger = logging.getLogger("docker_spacy_extract")

# Docker image name
DOCKER_IMAGE = "hc-tap-spacy"
DOCKERFILE_PATH = Path(__file__).resolve().parents[2] / "Dockerfile.spacy"


class DockerSpacyExtractor:
    """
    Extract entities using spaCy running in Docker.
    
    This bypasses local environment issues by running spaCy in
    a controlled Docker container with Python 3.11.
    """
    
    def __init__(self):
        """Initialize Docker-based extractor."""
        self._ensure_image_built()
    
    def _ensure_image_built(self):
        """Ensure Docker image is built."""
        # Check if image exists
        try:
            result = subprocess.run(
                ["docker", "images", "-q", DOCKER_IMAGE],
                capture_output=True,
                text=True,
                check=True
            )
            
            if result.stdout.strip():
                logger.info(f"Docker image {DOCKER_IMAGE} already exists")
                return
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"Failed to check Docker image: {e}")
        
        # Build image if it doesn't exist
        logger.info(f"Building Docker image {DOCKER_IMAGE}...")
        try:
            subprocess.run(
                [
                    "docker", "build",
                    "-f", str(DOCKERFILE_PATH),
                    "-t", DOCKER_IMAGE,
                    "."
                ],
                check=True,
                cwd=str(DOCKERFILE_PATH.parent)
            )
            logger.info(f"Successfully built Docker image {DOCKER_IMAGE}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to build Docker image: {e}")
    
    def extract(self, text: str, note_id: str, run_id: str) -> List[dict]:
        """
        Extract entities from text using Docker-based spaCy.
        
        Args:
            text: Clinical note text
            note_id: Note identifier
            run_id: ETL run identifier
            
        Returns:
            List of entity dicts
        """
        if not text or not text.strip():
            return []
        
        # Prepare input data
        input_data = {
            "text": text,
            "note_id": note_id,
            "run_id": run_id
        }
        
        try:
            # Run Docker container with input
            result = subprocess.run(
                [
                    "docker", "run",
                    "--rm",  # Remove container after run
                    "-i",    # Interactive (accept stdin)
                    "--platform", "linux/amd64",  # Force x86_64 platform
                    DOCKER_IMAGE,
                    "-c",
                    """
import sys
import json
from spacy_extract import SpacyExtractor

# Read input
input_data = json.loads(sys.stdin.read())

# Extract entities
extractor = SpacyExtractor()
entities = extractor.extract(
    input_data['text'],
    input_data['note_id'],
    input_data['run_id']
)

# Output as JSON
print(json.dumps(entities))
"""
                ],
                input=json.dumps(input_data),
                capture_output=True,
                text=True,
                check=True,
                timeout=60  # 60 second timeout
            )
            
            # Parse output
            entities = json.loads(result.stdout.strip())
            logger.debug(f"Extracted {len(entities)} entities from note {note_id}")
            return entities
            
        except subprocess.TimeoutExpired:
            logger.error(f"Docker extraction timed out for note {note_id}")
            return []
        except subprocess.CalledProcessError as e:
            logger.error(f"Docker extraction failed for note {note_id}: {e.stderr}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Docker output for note {note_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in Docker extraction for note {note_id}: {e}")
            return []


def build_image():
    """Build the Docker image (utility function)."""
    logger.info("Building spaCy Docker image...")
    try:
        subprocess.run(
            [
                "docker", "build",
                "-f", str(DOCKERFILE_PATH),
                "-t", DOCKER_IMAGE,
                "."
            ],
            check=True,
            cwd=str(DOCKERFILE_PATH.parent)
        )
        logger.info("Successfully built Docker image")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to build Docker image: {e}")
        return False


if __name__ == "__main__":
    # Test the extractor
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        # Build image
        success = build_image()
        sys.exit(0 if success else 1)
    
    # Test extraction
    extractor = DockerSpacyExtractor()
    test_text = "Patient presents with chest pain and hypertension. Started on aspirin 81mg and lisinopril 10mg."
    entities = extractor.extract(test_text, "test_note", "docker-spacy")
    
    print(f"Extracted {len(entities)} entities:")
    for ent in entities:
        print(f"  - {ent['text']} ({ent['entity_type']})")
