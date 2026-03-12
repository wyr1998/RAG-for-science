"""
Step 2: Extract figures from PDFs using PDFFigures2.

Supports two modes:
- JAR mode: if a fat JAR is found (pdffigures2.jar or *assembly*.jar in target/scala-2.12/),
  runs `java -jar <jar> ...` using Java from BUNDLED_JRE_DIR, JAVA_HOME, or PATH.
- sbt fallback: otherwise runs sbt runMain from the pdffigures2 repo (requires Java + sbt).

After extraction, this script normalizes the figure JSON so that page numbers
are 1-based (real page numbers), instead of the 0-based indices returned by PDFFigures2.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _resolve_java_executable() -> str | Path:
    """
    Resolve the Java executable for running the pdffigures2 JAR.
    Order: BUNDLED_JRE_DIR/bin/java[.exe], JAVA_HOME/bin/java[.exe], then "java" (PATH).
    """
    is_win = sys.platform.startswith("win")
    java_name = "java.exe" if is_win else "java"

    bundled = os.environ.get("BUNDLED_JRE_DIR")
    if bundled:
        path = Path(bundled).resolve() / "bin" / java_name
        if path.is_file():
            return path

    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        path = Path(java_home).resolve() / "bin" / java_name
        if path.is_file():
            return path

    return "java"


def _resolve_pdffigures2_jar(pdffigures2_dir: Path) -> Path | None:
    """
    Resolve the runnable (fat) JAR for PDFFigures2. Does not return the thin packageBin JAR.
    Checks: (1) pdffigures2_dir/pdffigures2.jar, (2) any *assembly*.jar in target/scala-2.12/.
    """
    root_jar = pdffigures2_dir / "pdffigures2.jar"
    if root_jar.is_file():
        return root_jar
    target_dir = pdffigures2_dir / "target" / "scala-2.12"
    if target_dir.is_dir():
        assembly_jars = sorted(target_dir.glob("*assembly*.jar"))
        if assembly_jars:
            return max(assembly_jars, key=lambda p: p.stat().st_size)
    return None


def extract_figures_with_pdffigures2(
    pdf_dir: str | Path,
    output_dir: str | Path,
    pdffigures2_dir: str | Path,
    stats_file: str | Path | None = None,
):
    """
    Run PDFFigures2's FigureExtractorBatchCli on a directory of PDFs.

    Args:
        pdf_dir: Directory containing PDF files (input for PDFFigures2)
        output_dir: Directory where JSON metadata (and optional images) will be written
        pdffigures2_dir: Path to the cloned `pdffigures2` repository
        stats_file: Optional path for PDFFigures2 statistics JSON
    """
    pdf_dir = Path(pdf_dir).resolve()
    output_dir = Path(output_dir).resolve()
    pdffigures2_dir = Path(pdffigures2_dir).resolve()

    if not pdf_dir.is_dir():
        raise NotADirectoryError(f"pdf_dir must be a directory: {pdf_dir}")
    if not pdffigures2_dir.is_dir():
        raise NotADirectoryError(f"pdffigures2_dir must be a directory: {pdffigures2_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    if stats_file is None:
        stats_file = output_dir / "pdffigures2_stats.json"
    else:
        stats_file = Path(stats_file).resolve()

    # PDFFigures2 uses a "prefix" for -d (data) and -m (images). We only use -d here.
    data_prefix = output_dir / "figures"

    # Use forward slashes so the sbt/Java CLI gets valid paths (avoids Windows backslash issues)
    pdf_dir_arg = pdf_dir.as_posix()
    stats_arg = stats_file.as_posix()
    data_prefix_arg = data_prefix.as_posix()

    log_path = output_dir / "pdffigures2_last_run.log"
    jar_path = _resolve_pdffigures2_jar(pdffigures2_dir)

    if jar_path is not None:
        java_exe = _resolve_java_executable()

        # On Windows, Path.resolve() may produce an extended-length path
        # starting with '\\\\?\\'. Java's -jar flag does not accept this
        # prefix, so strip it if present.
        jar_arg = str(jar_path.resolve())
        if os.name == "nt" and jar_arg.startswith("\\\\?\\"):
            jar_arg = jar_arg[4:]

        argv = [
            str(java_exe),
            "-Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider",
            "-Dfile.encoding=UTF-8",
            "-jar",
            jar_arg,
            pdf_dir_arg,
            "-s",
            stats_arg,
            "-d",
            data_prefix_arg,
        ]
        print(f"Running PDFFigures2 (JAR) with: {java_exe}")
        print("Command:", " ".join(argv))
        print(f"Log file: {log_path}")
        with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
            result = subprocess.run(
                argv,
                cwd=str(output_dir),
                stdout=logf,
                stderr=subprocess.STDOUT,
            )
    else:
        sbt_args = (
            f"runMain org.allenai.pdffigures2.FigureExtractorBatchCli "
            f"{pdf_dir_arg} -s {stats_arg} -d {data_prefix_arg}"
        )
        cmd = f'sbt "{sbt_args}"'
        print(f"Running PDFFigures2 in: {pdffigures2_dir}")
        print("Command:", cmd)
        print(f"Log file: {log_path}")
        with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
            result = subprocess.run(
                cmd,
                cwd=str(pdffigures2_dir),
                shell=True,
                stdout=logf,
                stderr=subprocess.STDOUT,
            )

    if result.returncode != 0:
        with open(log_path, "r", encoding="utf-8", errors="replace") as logf:
            log_content = logf.read()
        print("\n--- PDFFigures2/sbt output ---")
        print(log_content)
        print("--- end log ---")
        raise RuntimeError(
            f"PDFFigures2 failed with exit code {result.returncode}. "
            f"Full log: {log_path}"
        )

    print(f"\nDone. Figure metadata JSON written under: {data_prefix}")
    print(f"Stats file: {stats_file}")

    # Post-process: correct page numbers in all figures*.json files
    # PDFFigures2 writes 0-based page indices (real page minus one).
    # We store real 1-based page numbers in the JSON.
    figure_json_files = sorted(output_dir.glob("figures*.json"))
    if not figure_json_files:
        print("No figures*.json files found for page correction.")
        return

    for fig_json_path in figure_json_files:
        try:
            with open(fig_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                print(f"Skipping non-list JSON file: {fig_json_path}")
                continue
            for fig in data:
                if "page" in fig and isinstance(fig["page"], (int, float)):
                    fig["page"] = int(fig["page"]) + 1
            with open(fig_json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Corrected page numbers (0-based -> 1-based) in: {fig_json_path}")
        except Exception as e:
            print(f"Warning: failed to correct page numbers in {fig_json_path}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract figures from PDFs using PDFFigures2 (step 2)."
    )
    parser.add_argument(
        "pdf_dir",
        type=str,
        help="Directory containing PDF files to process",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        required=True,
        help="Output directory for figure JSON files",
    )
    parser.add_argument(
        "--pdffigures2-dir",
        type=str,
        required=True,
        help="Path to cloned allenai/pdffigures2 repository",
    )
    parser.add_argument(
        "--stats-file",
        type=str,
        default=None,
        help="Optional path for PDFFigures2 statistics JSON (default: <output>/pdffigures2_stats.json)",
    )

    args = parser.parse_args()
    extract_figures_with_pdffigures2(
        pdf_dir=args.pdf_dir,
        output_dir=args.output,
        pdffigures2_dir=args.pdffigures2_dir,
        stats_file=args.stats_file,
    )


if __name__ == "__main__":
    main()

