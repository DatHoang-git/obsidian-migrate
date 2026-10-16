import argparse
import sys
from pathlib import Path

from .migrator import Migrator
from .reporter import print_plan, print_summary


class MigrationError(ValueError):
    """Raised when migration validation fails."""
    pass


def validate_paths(source: Path, destination: Path, force: bool) -> None:
    """Validate source and destination paths.

    Raises MigrationError (a ValueError subclass) on invalid configurations.
    """
    source = source.resolve()
    destination = destination.resolve()

    # Source must exist
    if not source.exists():
        raise MigrationError(f"Source vault does not exist: {source}")
    if not source.is_dir():
        raise MigrationError(f"Source is not a directory: {source}")

    # Source == destination
    if source == destination:
        raise MigrationError(f"Source and destination are the same: {source}")

    # Destination inside source
    try:
        destination.relative_to(source)
    except ValueError:
        pass  # Not inside source, good
    else:
        raise MigrationError(
            f"Destination is inside the source vault:\n"
            f"  Source:      {source}\n"
            f"  Destination: {destination}\n"
            f"  This could cause recursive scanning issues."
        )

    # Source inside destination
    try:
        source.relative_to(destination)
    except ValueError:
        pass
    else:
        raise MigrationError(
            f"Source is inside the destination:\n"
            f"  Source:      {source}\n"
            f"  Destination: {destination}"
        )

    # Destination exists and non-empty
    if destination.exists():
        if destination.is_file():
            raise MigrationError(f"Destination exists and is a file: {destination}")
        # Check if non-empty
        if any(destination.iterdir()):
            if not force:
                raise MigrationError(
                    f"Destination exists and is not empty: {destination}\n"
                    f"  Use --force to overwrite."
                )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog='obsidian-migrate',
        description='Selectively migrate Class notes from an Obsidian vault into a new independent vault.',
    )
    parser.add_argument('source', type=Path, help='Path to the source Obsidian vault (read-only).')
    parser.add_argument('destination', type=Path, help='Path to the destination vault.')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be copied without actually copying.')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Print detailed progress information.')
    parser.add_argument('--force', action='store_true',
                        help='Allow overwriting a non-empty destination.')
    parser.add_argument('--include-obsidian', action='store_true',
                        help='Also copy the .obsidian/ configuration directory.')

    args = parser.parse_args()

    source = args.source.resolve()
    destination = args.destination.resolve()

    try:
        validate_paths(source, destination, args.force)
    except MigrationError as e:
        print(f"✖ {e}", file=sys.stderr)
        sys.exit(1)

    migrator = Migrator(source, destination, verbose=args.verbose)

    if args.verbose:
        print(f"Scanning vault: {source}", file=sys.stderr)

    plan = migrator.plan()

    if args.dry_run:
        print_plan(plan, dry_run=True)
        return

    # Create destination if needed
    destination.mkdir(parents=True, exist_ok=True)

    copied = migrator.execute(plan)

    # Copy .obsidian if requested
    if args.include_obsidian:
        obsidian_dir = source / '.obsidian'
        if obsidian_dir.exists():
            import shutil
            dest_obsidian = destination / '.obsidian'
            if dest_obsidian.exists():
                shutil.rmtree(str(dest_obsidian))
            shutil.copytree(str(obsidian_dir), str(dest_obsidian))
            if args.verbose:
                print(f"  COPY: .obsidian/ (configuration)", file=sys.stderr)

    print_summary(plan, copied)

if __name__ == '__main__':
    main()
