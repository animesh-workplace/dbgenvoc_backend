import json
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

# =====================
# CONFIG
# =====================
TOKEN = "a1689f50-055c-44e4-904d-be9a842ce056"  # <-- replace with your real token
GENE_FILE = "genes.txt"
OUTPUT_DIR = Path("oncokb_results")

URL = "https://www.oncokb.org/api/private/search/variants/clinical"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 OPR/126.0.0.0"
    ),
    "Referer": "https://www.oncokb.org/actionable-genes",
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json",
}

console = Console()


def read_genes(path: str):
    with open(path) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def fetch_and_save(client: httpx.Client, gene: str):
    params = {
        "hugoSymbol": gene,
        "germline": "false",
    }

    r = client.get(URL, headers=HEADERS, params=params)
    r.raise_for_status()

    out_file = OUTPUT_DIR / f"{gene}.json"
    with out_file.open("w") as f:
        json.dump(r.json(), f, indent=2)

    return out_file


def main():
    genes = read_genes(GENE_FILE)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Genes loaded:[/bold] {len(genes)}")
    console.print(f"[bold]Output dir:[/bold] {OUTPUT_DIR}\n")

    with httpx.Client(timeout=30.0) as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching gene data", total=len(genes))

            for gene in genes:
                try:
                    out = fetch_and_save(client, gene)
                    console.log(f"[green]Saved[/green] {out}")
                except Exception as e:
                    console.log(f"[red]Failed[/red] {gene}: {e}")

                progress.advance(task)


if __name__ == "__main__":
    main()
