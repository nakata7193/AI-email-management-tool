"""Main CLI entry point for AI Email Management Tool.

This module handles:
- CLI argument parsing
- Result formatting and display

Business logic lives in services/email_service.py.
Object creation is handled by services/container.py.
"""

import click
import logging
from typing import Optional

from services.container import ServiceContainer
from utils.formatting import (
    print_email_table, print_summary,
    print_success, print_error, print_info, print_warning,
    print_sender_table
)
from config import ProfileManager, get_config, load_categories, save_categories, category_to_folder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class CustomGroup(click.Group):
    """Custom Click group with enhanced error messages."""

    def parse_args(self, ctx, args):
        """Override parse_args to catch --profile without argument."""
        try:
            return super().parse_args(ctx, args)
        except click.ClickException as e:
            # Check if it's a profile-related error
            error_msg = str(e.message) if hasattr(e, 'message') else str(e)
            if "--profile" in error_msg and "requires an argument" in error_msg:
                self.show_profile_help()
                ctx.exit(1)
            raise

    def show_profile_help(self):
        """Show helpful message when --profile is used without argument."""
        try:
            mgr = ProfileManager()
            profiles = mgr.list_profiles()
            active = mgr.get_active_profile()

            click.echo("Error: Option '--profile' requires an argument.\n", err=True)

            if profiles:
                click.echo("Available profiles:", err=True)
                for prof in sorted(profiles.keys()):
                    if prof == active:
                        click.echo(f"  • {prof} (active)", err=True)
                    else:
                        click.echo(f"  • {prof}", err=True)

                click.echo("\nUsage:", err=True)
                click.echo("  python main.py --profile <name> <command>", err=True)
                click.echo("\nExample:", err=True)
                click.echo(f"  python main.py --profile {sorted(profiles.keys())[0]} inbox", err=True)
            else:
                click.echo("No profiles found. Create one with:", err=True)
                click.echo("  python main.py profile create <name> --description \"...\" --provider gmail", err=True)

        except Exception:
            # Fallback to default error message
            click.echo("Error: Option '--profile' requires an argument.", err=True)
            click.echo("Use 'python main.py --help' for more information.", err=True)


def get_profile_help_text():
    """Generate help text for profile option."""
    return "Use specific profile"


def validate_profile(ctx, param, value):
    """Validate profile option and show available profiles on error."""
    if value is None:
        return value

    # Check if profile exists
    mgr = ProfileManager()
    profiles = mgr.list_profiles()

    if value not in profiles:
        available = list(profiles.keys())
        active = mgr.get_active_profile()

        error_msg = f"Profile '{value}' does not exist.\n\n"

        if available:
            error_msg += "Available profiles:\n"
            for prof in available:
                if prof == active:
                    error_msg += f"  • {prof} (active)\n"
                else:
                    error_msg += f"  • {prof}\n"
            error_msg += "\nUsage:\n"
            error_msg += f"  python main.py --profile <name> <command>\n"
            error_msg += f"\nExample:\n"
            error_msg += f"  python main.py --profile {available[0]} inbox"
        else:
            error_msg += "No profiles found. Create one with:\n"
            error_msg += "  python main.py profile create <name> --description \"...\" --provider gmail"

        raise click.BadParameter(error_msg)

    return value


@click.group(cls=CustomGroup)
@click.option('--profile', callback=validate_profile,
              help=get_profile_help_text(),
              metavar='NAME')
@click.pass_context
def cli(ctx, profile):
    """AI-powered email management tool using Claude."""
    ctx.ensure_object(dict)
    ctx.obj['profile'] = profile


REQUIRED_CATEGORIES = {
    'personal': 'Personal message, direct communication',
    'other': 'Does not fit any other category',
}


def _enforce_required_categories(categories: dict) -> dict:
    """Ensure personal and other are always present."""
    result = dict(categories)
    for name, desc in REQUIRED_CATEGORIES.items():
        if name not in result:
            result[name] = desc
    return result


@cli.command()
@click.option('--add', 'add_pair', nargs=2, metavar='NAME DESCRIPTION',
              help='Add a new category')
@click.option('--edit', 'edit_pair', nargs=2, metavar='NAME DESCRIPTION',
              help='Update the description of an existing category')
@click.option('--delete', 'delete_name', metavar='NAME',
              help='Delete a category by name (personal and other cannot be deleted)')
def categories(add_pair, edit_pair, delete_name):
    """Manage email categories for AI classification."""
    from rich.table import Table
    from rich.console import Console
    console = Console()

    # --- Non-interactive: --add flag ---
    if add_pair:
        name, desc = add_pair[0].strip().lower().replace(' ', '_'), add_pair[1].strip()
        cats = _enforce_required_categories(load_categories())
        cats[name] = desc
        save_categories(cats)
        print_success(f"Added category '{name}' → folder '{category_to_folder(name)}'")
        return

    # --- Non-interactive: --edit flag ---
    if edit_pair:
        name, desc = edit_pair[0].strip().lower().replace(' ', '_'), edit_pair[1].strip()
        cats = _enforce_required_categories(load_categories())
        if name not in cats:
            print_error(f"Category '{name}' not found. Use --add to create it.")
            return
        cats[name] = desc
        save_categories(cats)
        print_success(f"Updated category '{name}'")
        return

    # --- Non-interactive: --delete flag ---
    if delete_name:
        name = delete_name.strip().lower().replace(' ', '_')
        if name in REQUIRED_CATEGORIES:
            print_error(f"Cannot delete '{name}' — it is a required category")
            return
        cats = _enforce_required_categories(load_categories())
        if name not in cats:
            print_warning(f"Category '{name}' not found")
            return
        del cats[name]
        save_categories(cats)
        print_success(f"Deleted category '{name}'")
        return

    # --- Interactive setup ---
    existing = _enforce_required_categories(load_categories())

    console.print("\n[bold cyan]Email Category Setup[/bold cyan]")
    console.print("Categories tell the AI how to classify your emails.")
    console.print("[dim]'personal' and 'other' are always present and cannot be removed.[/dim]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan")
    table.add_column("Gmail Folder", style="green")
    table.add_column("Description", style="dim")
    for name, desc in existing.items():
        tag = " [dim](required)[/dim]" if name in REQUIRED_CATEGORIES else ""
        table.add_row(name + tag, category_to_folder(name), desc)
    console.print("[bold]Current categories:[/bold]")
    console.print(table)
    console.print()

    keep = click.confirm("Keep existing categories and add/edit more?", default=True)
    cats = dict(existing) if keep else {}

    console.print("[dim]Enter category name and description. Type 'done' as name when finished.[/dim]\n")

    while True:
        name = click.prompt("Category name", default="done").strip().lower().replace(' ', '_')
        if name == "done":
            break
        if not name:
            continue
        if name in REQUIRED_CATEGORIES:
            print_warning(f"'{name}' is a required category — its description can be edited but it cannot be removed")

        existing_desc = cats.get(name, "")
        desc = click.prompt(
            f"Description for '{name}' (optional)",
            default=existing_desc,
        ).strip()

        cats[name] = desc
        print_success(f"Saved: {name} → Gmail folder '{category_to_folder(name)}'")

    cats = _enforce_required_categories(cats)
    save_categories(cats)

    console.print()
    table2 = Table(show_header=True, header_style="bold magenta")
    table2.add_column("Category", style="cyan")
    table2.add_column("Gmail Folder", style="green")
    for name in cats:
        table2.add_row(name, category_to_folder(name))
    console.print("[bold green]Saved categories:[/bold green]")
    console.print(table2)
    console.print()
    print_success(f"email_config.json updated with {len(cats)} categories")
    print_info("Run 'python main.py categorize' to classify emails using these categories")
    print_info("Run 'python main.py categorize' to classify emails using these categories")


@cli.command()
@click.option('--provider', type=click.Choice(['gmail', 'imap']), required=True,
              help='Email provider to set up')
@click.pass_context
def setup(ctx, provider: str):
    """Set up email provider authentication."""
    profile = ctx.obj.get('profile')
    config = get_config(profile)

    try:
        container = ServiceContainer(config)

        if provider == 'gmail':
            print_info("Setting up Gmail OAuth2 authentication...")
            if profile:
                print_info(f"Setting up for profile: {profile}")
            print_info("This will open a browser window for authentication.")

            provider_obj = container.get_provider('gmail')
            provider_obj.connect()

            print_success("Gmail authentication successful!")
            print_info("Token saved for future use.")

        elif provider == 'imap':
            print_info("IMAP configuration should be set in .env file")
            if profile:
                print_info(f"Profile: {profile}")
                print_info(f"Required variables: {profile.upper()}_IMAP_SERVER, {profile.upper()}_IMAP_PORT, {profile.upper()}_IMAP_EMAIL, {profile.upper()}_IMAP_PASSWORD")
            else:
                print_info("Required variables: IMAP_SERVER, IMAP_PORT, IMAP_EMAIL, IMAP_PASSWORD")

            # Test IMAP connection
            provider_obj = container.get_provider('imap')
            provider_obj.connect()
            provider_obj.disconnect()

            print_success("IMAP connection successful!")

    except Exception as e:
        print_error(f"Setup failed: {e}")
        logger.error(f"Setup error: {e}", exc_info=True)


# Profile management commands
@cli.group()
def profile():
    """Manage email account profiles."""
    pass


@profile.command('create')
@click.argument('name')
@click.option('--description', required=True, help='Profile description')
@click.option('--provider', type=click.Choice(['gmail', 'imap']), required=True,
              help='Email provider type')
def profile_create(name: str, description: str, provider: str):
    """Create a new email profile."""
    try:
        mgr = ProfileManager()
        mgr.create_profile(name, description, provider)
        print_success(f"Profile '{name}' created successfully")
        print_success(f"Data directory created: data/{name}/")
        print_info(f"\nTo use this profile, run commands with: --profile {name}")
        print_info(f"Or set it as active: python main.py profile use {name}")

        if provider == 'gmail':
            print_info(f"\n📝 Next steps:")
            print_info(f"1. Download Gmail credentials from Google Cloud Console")
            print_info(f"   Save to: data/{name}/credentials.json")
            print_info(f"2. Authenticate: python main.py --profile {name} setup --provider gmail")
            print_info(f"3. Fetch emails: python main.py --profile {name} fetch --limit 100")
        else:
            print_info(f"\n📝 Next steps:")
            print_info(f"1. Set up IMAP credentials in .env:")
            print_info(f"   {name.upper()}_IMAP_SERVER=imap.example.com")
            print_info(f"   {name.upper()}_IMAP_PORT=993")
            print_info(f"   {name.upper()}_IMAP_EMAIL=your.email@example.com")
            print_info(f"   {name.upper()}_IMAP_PASSWORD=your_password")
            print_info(f"2. Test connection: python main.py --profile {name} setup --provider imap")

    except Exception as e:
        print_error(f"Failed to create profile: {e}")


@profile.command('list')
def profile_list():
    """List all profiles."""
    mgr = ProfileManager()
    profiles = mgr.list_profiles()
    active = mgr.get_active_profile()

    if not profiles:
        print_info("No profiles configured")
        print_info("Create one with: python main.py profile create <name> --description '<desc>' --provider <gmail|imap>")
        return

    from rich.table import Table
    from rich.console import Console

    console = Console()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Provider", style="green")
    table.add_column("Active", style="yellow")

    for name, data in profiles.items():
        is_active = "✓" if name == active else ""
        table.add_row(name, data['description'], data['provider'], is_active)

    console.print("\n[bold]Email Profiles[/bold]")
    console.print(table)
    console.print()


@profile.command('use')
@click.argument('name')
def profile_use(name: str):
    """Set the active profile."""
    try:
        mgr = ProfileManager()
        mgr.set_active_profile(name)
        print_success(f"Active profile set to: {name}")
        print_info("All commands will now use this profile by default")
    except ValueError as e:
        print_error(str(e))


@profile.command('delete')
@click.argument('name')
@click.confirmation_option(prompt='Are you sure you want to delete this profile?')
def profile_delete(name: str):
    """Delete a profile."""
    mgr = ProfileManager()
    mgr.delete_profile(name)
    print_success(f"Profile '{name}' deleted")
    print_warning("Note: This does not delete cached emails or authentication tokens")


@cli.command()
@click.option('--provider', type=click.Choice(['gmail', 'imap', 'all']), default='all',
              help='Email provider to fetch from')
@click.option('--limit', default=50, help='Maximum number of emails to fetch')
@click.option('--unread-only', is_flag=True, help='Only fetch unread emails')
@click.option('--batch-size', default=100, help='Number of emails to store per batch')
@click.pass_context
def fetch(ctx, provider: str, limit: int, unread_only: bool, batch_size: int):
    """Fetch emails from provider and store in local database."""
    profile = ctx.obj.get('profile')
    config = get_config(profile)

    try:
        # Create container
        with ServiceContainer(config) as container:
            service = container.email_service

            # Determine which providers to fetch from
            providers_to_fetch = []

            if provider == 'all' or provider == 'gmail':
                providers_to_fetch.append(('gmail', container.get_provider('gmail')))

            if provider == 'all' or provider == 'imap':
                providers_to_fetch.append(('imap', container.get_provider('imap')))

            total_fetched = 0

            for provider_name, provider_obj in providers_to_fetch:
                try:
                    print_info(f"Fetching emails from {provider_name}...")
                    if profile:
                        print_info(f"Using profile: {profile}")

                    if limit > 1000:
                        print_info(f"Large fetch: {limit} emails with parallel processing")
                        print_info(f"Batch size: {batch_size} emails per commit")

                    provider_obj.connect()

                    # Use service layer for fetching
                    for progress in service.fetch_and_store_emails(
                        provider_obj,
                        provider_name,
                        limit,
                        batch_size,
                        unread_only
                    ):
                        print_success(
                            f"Batch {progress.batch_num}: Fetched & stored {progress.total_stored}/{progress.total_requested}. "
                            f"DB total: {progress.db_count}"
                        )

                    # Get final counts
                    provider_count = container.cache.get_count(provider=provider_name)
                    total_fetched += progress.total_stored

                    provider_obj.disconnect()
                    print_success(f"✓ Successfully fetched and stored {progress.total_stored} emails from {provider_name}")
                    print_info(f"✓ Database verification: {provider_count} {provider_name} emails in DB")

                except Exception as e:
                    print_error(f"Failed to fetch from {provider_name}: {e}")
                    logger.error(f"Fetch error for {provider_name}: {e}", exc_info=True)

            # Final total count
            final_count = container.cache.get_count()

            print_success(f"✓ Total emails fetched: {total_fetched}")
            print_success(f"✓ Total emails in database: {final_count}")
            print_info(f"Database location: {config['database'].path}")

    except Exception as e:
        print_error(f"Fetch failed: {e}")
        logger.error(f"Fetch error: {e}", exc_info=True)


@cli.command()
@click.argument('email_id')
@click.pass_context
def summarize(ctx, email_id: str):
    """Summarize a specific email."""
    profile = ctx.obj.get('profile')
    config = get_config(profile)

    try:
        with ServiceContainer(config) as container:
            service = container.email_service
            summarizer = container.summarizer

            result = service.get_email_summary(summarizer, email_id)

            if not result:
                print_error(f"Email with ID {email_id} not found")
                return

            if result.from_cache:
                print_info("Using cached summary")

            print_summary(result.summary, result.action_items)

    except Exception as e:
        print_error(f"Summarization failed: {e}")
        logger.error(f"Summarization error: {e}", exc_info=True)


@cli.command()
@click.argument('query')
@click.option('--limit', default=20, help='Maximum results to return')
@click.pass_context
def search(ctx, query: str, limit: int):
    """Search emails using natural language."""
    profile = ctx.obj.get('profile')
    config = get_config(profile)

    try:
        with ServiceContainer(config) as container:
            service = container.email_service
            searcher = container.searcher

            print_info(f"Searching for: '{query}'")

            result = service.search_emails(searcher, query, limit)

            if result.count == 0:
                print_warning("No emails found matching your query")
                return

            print_info(f"Found {result.count} results")
            print_email_table(result.results, show_category=True)

    except Exception as e:
        print_error(f"Search failed: {e}")
        logger.error(f"Search error: {e}", exc_info=True)


@cli.command()
@click.option('--limit', default=100, help='Maximum emails to categorize')
@click.option('--recategorize', default=None, metavar='CATEGORY',
              help='Recategorize emails: "all" to redo everything, or a category name (e.g. "newsletter") to redo that category only. Omit to categorize only uncategorized emails.')
@click.pass_context
def categorize(ctx, limit: int, recategorize: str):
    """Categorize emails using AI.

    By default only processes uncategorized emails.
    Use --recategorize to redo existing categories.
    """
    profile = ctx.obj.get('profile')
    config = get_config(profile)

    try:
        with ServiceContainer(config) as container:
            service = container.email_service
            categorizer = container.categorizer

            if recategorize:
                print_info(f"Recategorizing emails (filter: {recategorize})...")
            else:
                count = service.get_uncategorized_count(limit=limit)
                if count == 0:
                    print_info("All emails are already categorized")
                    return
                print_info(f"Categorizing {count} uncategorized emails...")

            processed = 0
            for i, total, email_data, category in service.categorize_emails(categorizer, limit, recategorize):
                processed = i
                if category == 'ERROR':
                    print_error(f"[{i}/{total}] Failed: {email_data['subject'][:50]}...")
                else:
                    print_info(f"[{i}/{total}] {email_data['subject'][:50]}... → {category}")

            if processed:
                print_success(f"Done! Processed {processed} emails")
            else:
                print_warning("No emails found to categorize")

    except Exception as e:
        print_error(f"Categorization failed: {e}")
        logger.error(f"Categorization error: {e}", exc_info=True)


@cli.command()
@click.option('--top', default=20, help='Show top N senders')
@click.option('--all', 'analyze_all', is_flag=True, help='Analyze ALL emails (not just a sample)')
@click.option('--sample-size', default=5000, help='Number of recent emails to analyze (ignored if --all is used)')
@click.option('--min-count', default=10, help='Minimum email count to show')
@click.pass_context
def analyze_senders(ctx, top: int, analyze_all: bool, sample_size: int, min_count: int):
    """Analyze Gmail to find top senders by email count.

    This command is fast and doesn't download full emails - only metadata.
    Use it to identify bulk senders (newsletters, spam, etc.)
    """
    profile = ctx.obj.get('profile')
    config = get_config(profile)

    try:
        with ServiceContainer(config) as container:
            if analyze_all:
                print_info("Analyzing ALL emails in inbox (this may take 30-45 minutes for 40K emails)...")
            else:
                print_info(f"Analyzing top senders from last {sample_size} emails...")
            print_info("(This only fetches metadata, not full emails - fast & lightweight)")

            gmail = container.get_provider('gmail')
            gmail.connect()

            sender_counts = gmail.analyze_top_senders(limit=None if analyze_all else sample_size)

            if not sender_counts:
                print_warning("No senders found")
                gmail.disconnect()
                return

            print_sender_table(sender_counts, top, min_count)
            gmail.disconnect()

    except Exception as e:
        print_error(f"Analysis failed: {e}")
        logger.error(f"Sender analysis error: {e}", exc_info=True)


@cli.command()
@click.option('--days', default=30, type=int, help='Keep emails fetched within this many days')
@click.pass_context
def clean(ctx, days: int):
    """Remove old emails from local cache database.

    Deletes emails that were fetched more than X days ago from your local
    SQLite database. This only affects your local cache - your emails in
    Gmail/IMAP remain untouched. You can always re-fetch deleted emails.

    Useful for keeping your local database size manageable.
    """
    profile = ctx.obj.get('profile')
    config = get_config(profile)

    try:
        with ServiceContainer(config) as container:
            service = container.email_service

            deleted = service.clean_old_emails(days)
            print_success(f"Cleaned {deleted} old emails from local cache (kept last {days} days)")

    except Exception as e:
        print_error(f"Clean failed: {e}")
        logger.error(f"Clean error: {e}", exc_info=True)


@cli.command()
@click.option('--category', default=None, metavar='CATEGORY',
              help='Only organize emails in this category (default: all categories)')
@click.option('--limit', default=500, help='Maximum number of emails to organize')
@click.option('--dry-run', is_flag=True, help='Preview changes without applying them to Gmail')
@click.pass_context
def organize(ctx, category: str, limit: int, dry_run: bool):
    """Apply AI categories as Gmail labels and move emails out of inbox.

    Reads category assignments from local database, creates matching Gmail labels
    if they don't exist, then applies the label to each email and removes it from
    the inbox — so emails appear in their category folder in Gmail.

    Use --dry-run to preview what would happen without making any changes.
    """
    profile = ctx.obj.get('profile')
    config = get_config(profile)

    try:
        with ServiceContainer(config) as container:
            service = container.email_service
            gmail = container.get_provider('gmail')
            gmail.connect()

            if dry_run:
                print_warning("Dry run — no changes will be made to Gmail")

            if category:
                print_info(f"Organizing emails in category: {category}")
            else:
                print_info("Organizing all categorized Gmail emails...")

            succeeded = 0
            failed = 0

            for i, total, subject, cat, success in service.organize_emails(
                gmail, category=category, limit=limit, dry_run=dry_run
            ):
                prefix = "[DRY RUN] " if dry_run else ""
                if success:
                    print_info(f"{prefix}[{i}/{total}] {subject[:50]!r} → {cat}")
                    succeeded += 1
                else:
                    print_error(f"{prefix}[{i}/{total}] Failed: {subject[:50]!r}")
                    failed += 1

            gmail.disconnect()

            if succeeded or failed:
                if dry_run:
                    print_success(f"Dry run complete: {succeeded} emails would be moved")
                else:
                    print_success(f"Done! Moved {succeeded} emails to category labels")
                    if failed:
                        print_warning(f"{failed} emails failed — check logs for details")
            else:
                print_warning("No categorized Gmail emails found. Run 'categorize' first.")

    except Exception as e:
        print_error(f"Organize failed: {e}")
        logger.error(f"Organize error: {e}", exc_info=True)


if __name__ == '__main__':
    cli()
