from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from .export import export_package
from .pipeline import create_claim_package


def main() -> None:
    st.set_page_config(page_title="ClaimKit Local", page_icon="🧰", layout="wide")
    st.title("ClaimKit Local")
    st.caption("Build a reviewable warranty evidence package. Files stay on this device.")
    language = st.selectbox("Document language", ["en", "ru"])
    description = st.text_area("Describe the reported problem")
    uploads = st.file_uploader(
        "Receipt, warranty card, serial label, overview and damage photos",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
    )
    if not uploads or not st.button("Inspect evidence", type="primary"):
        st.info("Try `claimkit demo` for a model-free synthetic walkthrough.")
        return
    with tempfile.TemporaryDirectory(prefix="claimkit-") as temp:
        folder = Path(temp) / "evidence"
        folder.mkdir()
        for upload in uploads:
            (folder / upload.name).write_bytes(upload.getvalue())
        try:
            package, evidence = create_claim_package(folder, language, description)
        except RuntimeError as exc:
            st.error(str(exc))
            return
        st.subheader("1. Evidence review")
        st.dataframe(
            [
                {
                    "file": item.path.name,
                    "type": item.file_type,
                    "warnings": ", ".join(item.quality_warnings),
                }
                for item in evidence
            ],
            use_container_width=True,
        )
        st.subheader("2. Extracted fields")
        st.dataframe([field.model_dump() for field in package.extracted_fields], use_container_width=True)
        st.subheader("3. Conflicts")
        if package.conflicts:
            st.warning("Resolve these values before sending a real claim.")
            st.json([conflict.model_dump() for conflict in package.conflicts])
        else:
            st.success("No cross-document conflicts found.")
        st.subheader("4. Package preview")
        st.json(package.model_dump(mode="json"))
        output = Path(temp) / "claim-package"
        archive = export_package(output, package, evidence, language)
        st.download_button("Download claim package", archive.read_bytes(), archive.name, "application/zip")


if __name__ == "__main__":
    main()
