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
    print_statistics, print_success, print_error, print_info, print_warning
)
from config import ProfileManager, get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


@click.group()
@click.option('--profile', help='Use specific profile')
@click.pass_context
def cli(ctx, profile):
    """AI-powered email management tool using Claude."""
    ctx.ensure_object(dict)
    ctx.obj['profile'] = profile


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
    """Fetch emails from provider and store them directly in database."""
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
@click.option('--category', help='Filter by category')
@click.option('--unread', is_flag=True, help='Show only unread emails')
@click.option('--limit', default=50, help='Maximum number of emails to display')
@click.pass_context
def inbox(ctx, category: Optional[str], unread: bool, limit: int):
    """Display inbox with categorized emails."""
    profile = ctx.obj.get('profile')
    config = get_config(profile)

    try:
        with ServiceContainer(config) as container:
            service = container.email_service

            if profile:
                print_info(f"Viewing inbox for profile: {profile}")

            emails = service.get_emails(
                limit=limit,
                unread_only=unread,
                category=category
            )

            if not emails:
                print_warning("No emails found matching criteria")
                return

            print_email_table(emails, show_category=True)

    except Exception as e:
        print_error(f"Failed to display inbox: {e}")
        logger.error(f"Inbox error: {e}", exc_info=True)


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
@click.pass_context
def categorize_all(ctx, limit: int):
    """Categorize all uncategorized emails."""
    profile = ctx.obj.get('profile')
    config = get_config(profile)

    try:
        with ServiceContainer(config) as container:
            service = container.email_service
            categorizer = container.categorizer

            # Check if there are uncategorized emails
            uncategorized_count = service.get_uncategorized_count(limit=limit)

            if uncategorized_count == 0:
                print_info("All emails are already categorized")
                return

            print_info(f"Categorizing {uncategorized_count} emails...")

            # Use service layer for categorization
            for i, total, email_data, category in service.categorize_uncategorized_emails(categorizer, limit):
                if category == 'ERROR':
                    print_error(f"[{i}/{total}] Failed to categorize: {email_data['subject'][:50]}...")
                else:
                    print_info(f"[{i}/{total}] Categorized: {email_data['subject'][:50]}... → {category}")

            print_success(f"Categorization complete! Processed {uncategorized_count} emails")

    except Exception as e:
        print_error(f"Categorization failed: {e}")
        logger.error(f"Categorization error: {e}", exc_info=True)


@cli.command()
@click.pass_context
def stats(ctx):
    """Display email statistics."""
    profile = ctx.obj.get('profile')
    config = get_config(profile)

    try:
        with ServiceContainer(config) as container:
            service = container.email_service

            if profile:
                print_info(f"Statistics for profile: {profile}")

            statistics = service.get_statistics()
            print_statistics(statistics)

    except Exception as e:
        print_error(f"Failed to get statistics: {e}")
        logger.error(f"Statistics error: {e}", exc_info=True)


@cli.command()
@click.argument('query')
@click.option('--limit', default=50, help='Maximum results to return')
@click.pass_context
def gmail_search(ctx, query: str, limit: int):
    """Search Gmail directly without fetching all emails first.

    Uses Gmail's native search syntax. Examples:
    - "from:sender@example.com"
    - "subject:meeting"
    - "has:attachment after:2024/01/01"
    """
    profile = ctx.obj.get('profile')
    config = get_config(profile)

    try:
        with ServiceContainer(config) as container:
            print_info(f"Searching Gmail for: '{query}'")

            gmail = container.get_provider('gmail')
            gmail.connect()

            emails = gmail.search_gmail(query, limit)

            if not emails:
                print_warning("No emails found matching your query")
                gmail.disconnect()
                return

            print_info(f"Found {len(emails)} results")

            # Convert to display format
            email_dicts = []
            for email in emails:
                email_dicts.append({
                    'id': email.id,
                    'subject': email.subject,
                    'sender': email.sender,
                    'recipient': email.recipient,
                    'received_date': email.received_date.isoformat() if hasattr(email.received_date, 'isoformat') else str(email.received_date),
                    'is_read': email.is_read,
                    'has_attachments': email.has_attachments,
                    'category': None
                })

            print_email_table(email_dicts, show_category=False)
            gmail.disconnect()

    except Exception as e:
        print_error(f"Gmail search failed: {e}")
        logger.error(f"Gmail search error: {e}", exc_info=True)


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

            # Sort by count
            sorted_senders = sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)

            # Filter by min count
            filtered_senders = [(sender, count) for sender, count in sorted_senders if count >= min_count]

            if not filtered_senders:
                print_warning(f"No senders with at least {min_count} emails")
                gmail.disconnect()
                return

            # Display results
            from rich.table import Table
            from rich.console import Console

            console = Console()
            table = Table(show_header=True, header_style="bold magenta", title=f"Top {top} Email Senders")

            table.add_column("Rank", style="dim", width=6)
            table.add_column("Sender", style="cyan", width=60)
            table.add_column("Count", style="yellow", width=10, justify="right")
            table.add_column("% of Total", style="green", width=12, justify="right")

            total_analyzed = sum(sender_counts.values())

            for i, (sender, count) in enumerate(filtered_senders[:top], 1):
                percentage = (count / total_analyzed) * 100

                # Clean up sender name for display
                display_name = sender[:58] + "..." if len(sender) > 60 else sender

                table.add_row(
                    f"#{i}",
                    display_name,
                    str(count),
                    f"{percentage:.1f}%"
                )

            console.print()
            console.print(table)
            console.print()

            # Summary
            top_n_total = sum(count for _, count in filtered_senders[:top])
            top_n_percentage = (top_n_total / total_analyzed) * 100

            print_info(f"📊 Summary:")
            print_info(f"   • Total emails analyzed: {total_analyzed:,}")
            print_info(f"   • Unique senders: {len(sender_counts):,}")
            print_info(f"   • Top {top} senders: {top_n_total:,} emails ({top_n_percentage:.1f}% of total)")
            print_info(f"   • Senders with {min_count}+ emails: {len(filtered_senders)}")

            gmail.disconnect()

    except Exception as e:
        print_error(f"Analysis failed: {e}")
        logger.error(f"Sender analysis error: {e}", exc_info=True)


@cli.command()
@click.option('--days', default=30, type=int, help='Days to keep (default: 30)')
@click.pass_context
def clean(ctx, days: int):
    """Clean old emails from cache."""
    profile = ctx.obj.get('profile')
    config = get_config(profile)

    try:
        with ServiceContainer(config) as container:
            service = container.email_service

            deleted = service.clean_old_emails(days)
            print_success(f"Cleaned {deleted} old emails from cache")

    except Exception as e:
        print_error(f"Clean failed: {e}")
        logger.error(f"Clean error: {e}", exc_info=True)


if __name__ == '__main__':
    cli()
