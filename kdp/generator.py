"""Image providers for generation and optional image editing."""
from __future__ import annotations

import base64
import logging
import urllib.request
from pathlib import Path
from typing import Optional

import openai

from .utils import retry_with_backoff

log = logging.getLogger("kdp")

# ── Corrective suffixes appended on QA failures ───────────────────────────────

_QA_CORRECTIONS: dict[str, str] = {
    "grey":       "Use only pure black outlines on a plain white background — no grey shading, no fills.",
    "too_empty":  "Make the main subject larger with clear bold outlines and large enclosed coloring spaces. Keep the requested age and complexity; do not add tiny patterns.",
    "too_filled": "Use thinner outlines with open areas so children can colour it in — no solid fills.",
    "cropped":    "The whole illustration must fit inside the page with wide white margins on every side.",
    "background": "Plain white background only — no textures, gradients, or patterns behind the drawing.",
}


def _save_image(item, dest: Path) -> None:
    """Save one image response item — prefers b64_json, falls back to url."""
    if getattr(item, "b64_json", None):
        dest.write_bytes(base64.b64decode(item.b64_json))
    elif getattr(item, "url", None):
        with urllib.request.urlopen(item.url) as r:
            dest.write_bytes(r.read())
    else:
        raise RuntimeError("API response has neither b64_json nor url")


# ── Image generation ──────────────────────────────────────────────────────────

class ImageGenerator:
    def __init__(
        self,
        client: openai.OpenAI,
        model: str = "gpt-image-1",
        size: str = "1024x1536",
        quality: str = "medium",
    ) -> None:
        self.client  = client
        self.model   = model
        self.size    = size
        self.quality = quality

    # Decorated versions are created in generate() / edit() to allow
    # per-call max_attempts without re-wrapping the class method.

    def generate(
        self,
        prompt: str,
        dest: Path,
        qa_flags: Optional[list[str]] = None,
        attempt: int = 0,
        max_attempts: int = 4,
    ) -> bool:
        """
        Generate one image into *dest*.
        On QA retries, qa_flags corrections are appended to the prompt.
        Returns True on success.
        """
        full_prompt = prompt
        if qa_flags:
            corrections = "  ".join(
                _QA_CORRECTIONS[f] for f in qa_flags if f in _QA_CORRECTIONS
            )
            if corrections:
                full_prompt = prompt + "\n\nIMPORTANT CORRECTIONS: " + corrections

        @retry_with_backoff(max_attempts=max_attempts)
        def _call() -> None:
            resp = self.client.images.generate(
                model=self.model,
                prompt=full_prompt,
                size=self.size,
                quality=self.quality,
                n=1,
            )
            _save_image(resp.data[0], dest)

        try:
            _call()
            log.debug("Generated %s", dest.name)
            return True
        except Exception as exc:
            log.error("generate failed for %s: %s", dest.name, exc)
            return False

    def edit(
        self,
        source_path: Path,
        prompt: str,
        dest: Path,
        max_attempts: int = 3,
    ) -> bool:
        """
        Edit *source_path* with *prompt*, save result to *dest*.
        Returns True on success, False if the model/API doesn't support edits.
        """
        @retry_with_backoff(max_attempts=max_attempts)
        def _call() -> None:
            with open(source_path, "rb") as img_file:
                resp = self.client.images.edit(
                    model=self.model,
                    image=img_file,
                    prompt=prompt,
                    size=self.size,
                    quality=self.quality,
                    n=1,
                )
            _save_image(resp.data[0], dest)

        try:
            _call()
            log.debug("Edited %s -> %s", source_path.name, dest.name)
            return True
        except openai.BadRequestError as exc:
            # dall-e-3 does not support images.edit — fall back to generate
            log.warning("Image edit not supported by %s, falling back to generate: %s", self.model, exc)
            return self.generate(prompt, dest, max_attempts=max_attempts)
        except Exception as exc:
            log.error("edit failed for %s: %s", dest.name, exc)
            return False


class SchnellGenerator:
    """Replicate FLUX.1 Schnell adapter. Text-to-image only; no reference edits."""

    model = "black-forest-labs/flux-schnell"
    supports_edits = False

    def __init__(self, client, aspect_ratio: str = "3:4") -> None:
        self.client = client
        self.aspect_ratio = aspect_ratio

    def generate(
        self, prompt: str, dest: Path,
        qa_flags: Optional[list[str]] = None,
        attempt: int = 0, max_attempts: int = 4,
    ) -> bool:
        corrections = "  ".join(
            _QA_CORRECTIONS[f] for f in (qa_flags or []) if f in _QA_CORRECTIONS
        )
        full_prompt = prompt
        if corrections:
            full_prompt += "\n\nIMPORTANT CORRECTIONS: " + corrections

        # Only model requests are retried. A file download failure must not
        # silently trigger another billable image generation.
        @retry_with_backoff(max_attempts=max_attempts)
        def _predict():
            return self.client.run(self.model, input={
                "prompt": full_prompt,
                "aspect_ratio": self.aspect_ratio,
                "num_outputs": 1,
                "num_inference_steps": 4,
                "output_format": "png",
            })

        try:
            output = _predict()
            if not output:
                raise RuntimeError("Replicate returned no images")
            item = output[0]
            # Current SDK returns FileOutput; older releases returned URLs.
            if hasattr(item, "read"):
                image_bytes = item.read()
            elif isinstance(item, str) and item.startswith("https://"):
                with urllib.request.urlopen(item, timeout=60) as response:
                    image_bytes = response.read()
            else:
                raise RuntimeError("Unsupported Replicate image response")
            if not image_bytes:
                raise RuntimeError("Replicate returned an empty image")
            dest.write_bytes(image_bytes)
            return True
        except Exception as exc:
            log.error("Schnell generation failed for %s: %s", dest.name, exc)
            return False

    def edit(self, source_path: Path, prompt: str, dest: Path,
             max_attempts: int = 3) -> bool:
        log.warning("Schnell does not support image editing; colored sample skipped")
        return False
