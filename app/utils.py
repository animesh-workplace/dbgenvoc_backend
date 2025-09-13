import re
from sqlalchemy import and_
from typing import Tuple, Optional
from app.core import get_model_class
from app.schema import GenomicRegionSuggestion

GENOMIC_TABLES = [
    "es_tcga",
    "wg_somatic",
    "es_journal",
    "exome_somatic",
    "targeted_somatic",
]


def parse_genomic_region(region_str: str) -> Optional[Tuple[str, int, Optional[int]]]:
    """
    Parse genomic region strings in various formats:
    - chr1:915188-1015188
    - chr11:534289
    - chr1:915,188-1,015,188
    - 1:915188-1015188
    - chrX:1000000-2000000
    """
    # Remove commas from numbers
    cleaned_str = re.sub(r",", "", region_str)

    # Pattern for chr:start-end or chr:start (end is optional)
    patterns = [
        r"^(chr)?(\w+):(\d+)-(\d+)$",  # chr1:100-200 or 1:100-200
        r"^(chr)?(\w+):(\d+)$",  # chr1:100 or 1:100
    ]

    for pattern in patterns:
        match = re.match(pattern, cleaned_str)
        if match:
            groups = match.groups()
            chrom = groups[1]  # chromosome number/name
            start = int(groups[2])

            # If end is provided, use it; otherwise end = start (single position)
            end = int(groups[3]) if len(groups) > 3 and groups[3] else start

            # Ensure chromosome format consistency
            chrom = f"chr{chrom}" if not chrom.startswith("chr") else chrom

            return chrom, start, end

    return None


def format_genomic_region(
    chromosome: str, start: int, end: Optional[int] = None
) -> str:
    """Format genomic region as string"""
    if end and end != start:
        return f"{chromosome}:{start}-{end}"
    else:
        return f"{chromosome}:{start}"


async def search_genomic_regions(chrom: str, start: int, end: int, limit: int, db):
    """Search for exact or overlapping genomic regions"""
    suggestions = []

    for table_name in GENOMIC_TABLES:
        try:
            model_class = get_model_class(table_name)

            if not (
                hasattr(model_class, "chromosome")
                and hasattr(model_class, "start")
                and hasattr(model_class, "end")
            ):
                continue

            # Search for regions that overlap with the query region
            query = (
                db.query(model_class)
                .filter(
                    and_(
                        model_class.chromosome == chrom,
                        model_class.start <= end,
                        model_class.end >= start,
                    )
                )
                .order_by(model_class.start)
                .limit(limit // len(GENOMIC_TABLES))  # Distribute limit across tables
            )

            results = query.all()

            for result in results:
                region_str = format_genomic_region(
                    result.chromosome, result.start, result.end
                )

                suggestions.append(
                    GenomicRegionSuggestion(
                        value=region_str,
                        type="genomic_region",
                        table=table_name,
                        chromosome=result.chromosome,
                        start=result.start,
                        end=result.end,
                    )
                )

        except Exception as e:
            # Skip tables that cause errors
            continue

    return suggestions[:limit]


async def search_partial_genomic_region(term: str, limit: int, db):
    """Search for partial genomic region matches (chromosome names, etc.)"""
    suggestions = []

    for table_name in GENOMIC_TABLES:
        try:
            model_class = get_model_class(table_name)

            if not (
                hasattr(model_class, "chromosome")
                and hasattr(model_class, "start")
                and hasattr(model_class, "end")
            ):
                continue

            # Search for chromosome names that match the term
            query = (
                db.query(model_class.chromosome, model_class.start, model_class.end)
                .filter(model_class.chromosome.ilike(f"{term}%"))
                .distinct()
                .order_by(model_class.chromosome, model_class.start)
                .limit(limit // len(GENOMIC_TABLES))
            )

            results = query.all()

            for chrom, start, end in results:
                region_str = format_genomic_region(chrom, start, end)

                suggestions.append(
                    GenomicRegionSuggestion(
                        value=region_str,
                        type="genomic_region",
                        table=table_name,
                        chromosome=chrom,
                        start=start,
                        end=end,
                    )
                )

        except Exception as e:
            # Skip tables that cause errors
            continue

    return suggestions[:limit]
