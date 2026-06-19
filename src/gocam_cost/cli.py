"""Command-line interface: build the triple DB and export derived artifacts."""
from __future__ import annotations

from pathlib import Path

import duckdb
import typer

from . import config as C
from . import db, gitdata, metrics, patterns
from .extract import extract_to_parquet
from .fetch import fetch_versions

app = typer.Typer(help="GO-CAM curation cost estimates from noctua-models history.", no_args_is_help=True)

RAW_DIR = C.VENDOR / "raw"


@app.command()
def build(concurrency: int = 32, skip_fetch: bool = False) -> None:
    """Full pipeline: clone timeline -> fetch contents -> extract -> DuckDB -> export."""
    typer.echo("[1/5] ensuring blobless clone ...")
    gitdata.ensure_clone()
    typer.echo("[2/5] enumerating native, non-bulk versions ...")
    versions = gitdata.enumerate_versions()
    typer.echo(f"      {len(versions)} versions across "
               f"{len({v.model_id for v in versions})} models")
    if not skip_fetch:
        typer.echo("[3/5] fetching model contents over HTTP ...")
        n, missing = fetch_versions(versions, concurrency=concurrency)
        typer.echo(f"      attempted {n} new blobs; {len(missing)} unavailable (skipped)")
    # keep only versions whose content is cached, so version_id indices stay aligned
    from .fetch import _cache_path
    versions = [v for v in versions if _cache_path(v.blob_oid).exists()]
    typer.echo("[4/5] extracting triples (pyoxigraph) ...")
    total = extract_to_parquet(versions, RAW_DIR)
    typer.echo(f"      {total:,} raw triples")
    typer.echo("[5/5] building DuckDB (skolemize + diff in SQL) ...")
    db.build(versions, RAW_DIR)
    from . import true_gocams
    true_gocams.fetch_index(force=True)  # refresh canonical True GO-CAM index
    export()


@app.command()
def export() -> None:
    """Write the small committed parquet that `publish` embeds into the notebook."""
    C.DATA.mkdir(parents=True, exist_ok=True)
    df = metrics.compute()
    df.to_parquet(C.DATA / "curation_metrics.parquet", index=False)

    con = duckdb.connect(str(C.DUCKDB_PATH), read_only=True)
    con.execute(f"COPY (SELECT * FROM versions) TO '{(C.DATA/'versions.parquet').as_posix()}' (FORMAT parquet);")
    con.close()

    reps = patterns.representatives(df)
    typer.echo(f"exported derived artifacts to {C.DATA}")
    typer.echo("\nrepresentative production examples:")
    for _, r in reps.iterrows():
        typer.echo(f"  [{r.pattern:13}] {r.model_id}  saves={r.n_saves} "
                   f"churn={r.total_churn} active60m={r.active_min_60m}min  {str(r.title)[:48]}")


@app.command()
def publish() -> None:
    """Regenerate the self-contained interactive marimo notebook (embeds data)."""
    from . import publish as pub
    out = pub.generate()
    typer.echo(f"wrote interactive notebook -> {out}")


@app.command()
def docs() -> None:
    """Publish the interactive notebook to docs/ as a WASM site (GitHub Pages)."""
    import subprocess
    from . import publish as pub
    nb = pub.generate()
    (C.ROOT / "docs").mkdir(exist_ok=True)
    subprocess.run(
        ["uv", "run", "marimo", "export", "html-wasm", str(nb),
         "-o", str(C.ROOT / "docs"), "--mode", "run", "--show-code", "-f"],
        check=True, cwd=C.ROOT,
    )
    (C.ROOT / "docs" / ".nojekyll").write_text("")
    typer.echo(f"published interactive docs -> {C.ROOT / 'docs'}")


@app.command()
def stats() -> None:
    """Print headline cohort summary."""
    df = metrics.compute()
    with __import__("pandas").option_context("display.width", 200, "display.max_columns", None):
        typer.echo(metrics.cohort_summary(df).to_string(index=False))


if __name__ == "__main__":
    app()
