from .migrator import MigrationPlan

def print_plan(plan: MigrationPlan, dry_run: bool = False) -> None:
    vault_rel = plan.vault_path
    dest_rel = plan.dest_path
    
    print(f"\nSource:")
    print(f"  {vault_rel}")
    print(f"\nDestination:")
    print(f"  {dest_rel}")
    
    print(f"\nClass seed notes:        {len(plan.seeds)}")
    print(f"Markdown dependencies:   {len(plan.markdown_deps)}")
    print(f"Asset dependencies:      {len(plan.asset_deps)}")
    print(f"Total selected files:    {len(plan.all_selected)}")
    print(f"\nUnresolved links:        {len(plan.unresolved)}")
    print(f"Ambiguous links:         {len(plan.ambiguous)}")
    
    if plan.unresolved:
        print(f"\nUnresolved links:")
        for u in plan.unresolved:
            print(f"  {u.source}  ->  {u.link}")
    
    if plan.ambiguous:
        print(f"\nAmbiguous links:")
        for a in plan.ambiguous:
            print(f"  {a.source}  ->  {a.link}")
            print(f"    Candidates:")
            for c in a.candidates:
                print(f"      {c}")
    
    print(f"\nFiles to copy:")
    for f in plan.all_selected:
        rel = f.relative_to(plan.vault_path)
        print(f"  {rel}")
    
    if dry_run:
        print(f"\nDry run complete.")
        print(f"No files were modified.")

def print_summary(plan: MigrationPlan, copied: int) -> None:
    print(f"\nMigration complete.")
    print(f"")
    print(f"Class seeds:             {len(plan.seeds)}")
    print(f"Markdown dependencies:   {len(plan.markdown_deps)}")
    print(f"Asset dependencies:      {len(plan.asset_deps)}")
    print(f"Total files copied:      {copied}")
    print(f"")
    print(f"Unresolved links:        {len(plan.unresolved)}")
    print(f"Ambiguous links:         {len(plan.ambiguous)}")
    
    if plan.unresolved:
        print(f"\nUnresolved links:")
        for u in plan.unresolved:
            print(f"  {u.source}  ->  {u.link}")
    
    if plan.ambiguous:
        print(f"\nAmbiguous links:")
        for a in plan.ambiguous:
            print(f"  {a.source}  ->  {a.link}")
            print(f"    Candidates:")
            for c in a.candidates:
                print(f"      {c}")
