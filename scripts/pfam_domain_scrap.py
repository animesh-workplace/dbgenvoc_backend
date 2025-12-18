import time
import math
import requests
import pandas as pd

# --- Configuration ---
INPUT_FILE = "hugo_symbols.list"
CHUNK_SIZE = 10  # Number of genes per API request
URL_PFAM = "https://v1.genomenexus.org/pfam/domain"
URL_TRANSCRIPTS = "https://v1.genomenexus.org/ensembl/transcript"


def read_hugo_symbols(filepath):
    """Reads gene symbols from a file, removing whitespace/empty lines."""
    try:
        with open(filepath, "r") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: The file '{filepath}' was not found.")
        return []


def fetch_transcripts_chunked(hugo_symbols):
    """
    Fetches transcript data in batches (chunks).
    """
    total_genes = len(hugo_symbols)
    all_results = []

    # Calculate number of chunks needed
    num_chunks = math.ceil(total_genes / CHUNK_SIZE)
    print(f"Processing {total_genes} symbols in {num_chunks} batches...")

    for i in range(0, total_genes, CHUNK_SIZE):
        # Create the current batch
        batch = hugo_symbols[i : i + CHUNK_SIZE]
        current_batch_num = (i // CHUNK_SIZE) + 1

        print(
            f"  [Batch {current_batch_num}/{num_chunks}] Fetching {len(batch)} genes...",
            end=" ",
        )

        try:
            headers = {"Content-Type": "application/json"}
            payload = {"hugoSymbols": batch}

            response = requests.post(URL_TRANSCRIPTS, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            all_results.extend(data)
            print("Success.")

        except requests.exceptions.RequestException as e:
            print(f"FAILED. Error: {e}")
            # Optional: Log failed symbols to a file if needed

        # Be polite to the API server
        time.sleep(0.5)

    return all_results


def fetch_pfam_details(pfam_ids):
    """
    Fetches Pfam domain descriptions for a list of IDs.
    Also chunked because a huge list of domains can fail too.
    """
    unique_ids = list(set(pfam_ids))
    total_ids = len(unique_ids)

    if total_ids == 0:
        return {}

    print(f"\nFetching details for {total_ids} unique Pfam domains (chunked)...")

    pfam_lookup = {}

    # Chunking Pfam requests as well
    for i in range(0, total_ids, CHUNK_SIZE):
        batch = unique_ids[i : i + CHUNK_SIZE]

        try:
            headers = {"Content-Type": "application/json"}
            payload = {"pfamDomainIds": batch}

            response = requests.post(URL_PFAM, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()

            # Update master lookup dict
            for d in data:
                # Some domains prefer 'pfamDomainDescription', others 'name'
                desc = d.get("pfamDomainDescription") or d.get("name") or "Unknown"
                pfam_lookup[d["pfamDomainId"]] = desc

        except requests.exceptions.RequestException as e:
            print(f"  Pfam Batch Error: {e}")

        time.sleep(0.2)

    return pfam_lookup


def process_data(raw_data):
    """
    Parses the nested JSON into three flat lists.
    """
    transcript_records = []
    exon_records = []
    domain_records = []

    pfam_ids_found = set()

    for item in raw_data:
        t_id = item.get("transcriptId")

        # 1. Transcript Data
        # Ensure hugoSymbols exists and is not empty
        symbols = item.get("hugoSymbols", [])
        gene_sym = symbols[0] if symbols else None

        transcript_records.append(
            {
                "transcript_id": t_id,
                "gene_symbol": gene_sym,
                "gene_id": item.get("geneId"),
                "protein_id": item.get("proteinId"),
                "protein_length": item.get("proteinLength"),
                "refseq_id": item.get("refseqMrnaId"),
                "uniprot_id": item.get("uniprotId"),
            }
        )

        # 2. Exon Data
        if "exons" in item:
            for exon in item["exons"]:
                exon_records.append(
                    {
                        "transcript_id": t_id,
                        "exon_id": exon.get("exonId"),
                        "rank": exon.get("rank"),
                        "strand": exon.get("strand"),
                        "start": exon.get("exonStart"),
                        "end": exon.get("exonEnd"),
                        "version": exon.get("version"),
                    }
                )

        # 3. Domain Data
        if "pfamDomains" in item:
            for dom in item["pfamDomains"]:
                p_id = dom.get("pfamDomainId")
                if p_id:
                    pfam_ids_found.add(p_id)
                    domain_records.append(
                        {
                            "transcript_id": t_id,
                            "pfam_id": p_id,
                            "start": dom.get("pfamDomainStart"),
                            "end": dom.get("pfamDomainEnd"),
                        }
                    )

    return transcript_records, exon_records, domain_records, list(pfam_ids_found)


def main():
    # 1. Load Inputs
    symbols = read_hugo_symbols(INPUT_FILE)
    if not symbols:
        return

    # 2. Fetch Main Data (Chunked)
    raw_data = fetch_transcripts_chunked(symbols)

    if not raw_data:
        print("No data retrieved.")
        return

    # 3. Flatten Data
    print("\nProcessing raw data...")
    transcripts, exons, domains, pfam_ids = process_data(raw_data)

    # 4. Fetch Pfam Names (Chunked)
    pfam_lookup = fetch_pfam_details(pfam_ids)

    # 5. Merge Pfam Names into Domain Records
    for d in domains:
        d["domain_name"] = pfam_lookup.get(
            d["pfam_id"], d["pfam_id"]
        )  # Fallback to ID if name not found

    # 6. Convert to DataFrames
    df_transcripts = pd.DataFrame(transcripts)
    df_exons = pd.DataFrame(exons)
    df_domains = pd.DataFrame(domains)

    # 7. Export
    print("\n--- Summary ---")
    print(f"Transcripts found: {len(df_transcripts)}")
    print(f"Exons found:       {len(df_exons)}")
    print(f"Domains found:     {len(df_domains)}")

    df_transcripts.to_csv("db_transcripts.csv", index=False)
    df_exons.to_csv("db_exons.csv", index=False)
    df_domains.to_csv("db_domains.csv", index=False)

    print("\nDone! Files saved.")


if __name__ == "__main__":
    main()
