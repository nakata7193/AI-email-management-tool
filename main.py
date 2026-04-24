"""Main CLI entry point for AI Email Management Tool."""

import click
import logging
from typing import Optional

from providers.gmail import GmailProvider
from providers.imap import IMAPProvider
from storage.cache import EmailCache
from ai.categorizer import EmailCategorizer
from ai.summarizer import EmailSummarizer
from ai.search import EmailSearcher
from utils.formatting import (
    print_email_table, print_email_detail, print_summary,
    print_statistics, print_success, print_error, print_info, print_warning
)
from config import app_config, ProfileManager, get_config

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
        if provider == 'gmail':
            print_info("Setting up Gmail OAuth2 authentication...")
            if profile:
                print_info(f"Setting up for profile: {profile}")
            print_info("This will open a browser window for authentication.")

            gmail = GmailProvider(config['gmail'])
            gmail.connect()

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
            imap = IMAPProvider(config['imap'])
            imap.connect()
            imap.disconnect()

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
        print_info(f"To use this profile, run commands with: --profile {name}")
        print_info(f"Or set it as active: python main.py profile use {name}")

        if provider == 'gmail':
            print_info(f"\nNext steps:")
            print_info(f"1. Set up Gmail credentials in .env:")
            print_info(f"   {name.upper()}_GMAIL_CREDENTIALS_FILE=credentials_{name}.json")
            print_info(f"   {name.upper()}_GMAIL_TOKEN_FILE=token_{name}.json")
            print_info(f"2. Run: python main.py --profile {name} setup --provider gmail")
        else:
            print_info(f"\nNext steps:")
            print_info(f"1. Set up IMAP credentials in .env:")
            print_info(f"   {name.upper()}_IMAP_SERVER=imap.example.com")
            print_info(f"   {name.upper()}_IMAP_PORT=993")
            print_info(f"   {name.upper()}_IMAP_EMAIL=your.email@example.com")
            print_info(f"   {name.upper()}_IMAP_PASSWORD=your_password")
            print_info(f"2. Run: python main.py --profile {name} setup --provider imap")

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
@click.pass_context
def fetch(ctx, provider: str, limit: int, unread_only: bool):
    """Fetch emails from provider and cache them."""
    profile = ctx.obj.get('profile')
    config = get_config(profile)
    cache = EmailCache(config['database'].path)

    try:
        providers_to_fetch = []

        if provider == 'all' or provider == 'gmail':
            providers_to_fetch.append(('gmail', GmailProvider(config['gmail'])))

        if provider == 'all' or provider == 'imap':
            providers_to_fetch.append(('imap', IMAPProvider(config['imap'])))

        total_fetched = 0

        for provider_name, provider_obj in providers_to_fetch:
            try:
                print_info(f"Fetching emails from {provider_name}...")
                if profile:
                    print_info(f"Using profile: {profile}")

                provider_obj.connect()
                emails = provider_obj.fetch_emails(limit=limit, unread_only=unread_only)

                print_info(f"Fetched {len(emails)} emails from {provider_name}")

                # Cache emails
                for email in emails:
                    cache.store_email(email, provider_name)

                total_fetched += len(emails)

                provider_obj.disconnect()

            except Exception as e:
                print_error(f"Failed to fetch from {provider_name}: {e}")
                logger.error(f"Fetch error for {provider_name}: {e}", exc_info=True)

        print_success(f"Total emails fetched and cached: {total_fetched}")

    finally:
        cache.close()

@cli.command()
@click.option('--category', help='Filter by category')
@click.option('--unread', is_flag=True, help='Show only unread emails')
@click.option('--limit', default=50, help='Maximum number of emails to display')
@click.pass_context
def inbox(ctx, category: Optional[str], unread: bool, limit: int):
    """Display inbox with categorized emails."""
    profile = ctx.obj.get('profile')
    config = get_config(profile)
    cache = EmailCache(config['database'].path)

    try:
        if profile:
            print_info(f"Viewing inbox for profile: {profile}")

        emails = cache.get_emails(
            limit=limit,
            unread_only=unread,
            category=category
        )

        if not emails:
            print_warning("No emails found matching criteria")
            return

        print_email_table(emails, show_category=True)

    finally:
        cache.close()

@cli.command()
@click.argument('email_id')
@click.option('--provider', help='Email provider (gmail/imap)')
@click.pass_context
def summarize(ctx, email_id: str, provider: Optional[str]):
    """Summarize a specific email."""
    profile = ctx.obj.get('profile')
    config = get_config(profile)
    cache = EmailCache(config['database'].path)
    summarizer = EmailSummarizer()

    try:
        # Get email from cache
        email_data = cache.get_emails(limit=1000)  # Get all to search by ID

        email = None
        for e in email_data:
            if e['id'] == email_id or str(e['id']).endswith(email_id):
                email = e
                break

        if not email:
            print_error(f"Email with ID {email_id} not found")
            return

        # Convert dict back to Email object
        from providers.base import Email
        from datetime import datetime

        email_obj = Email(
            id=email['id'],
            subject=email['subject'],
            sender=email['sender'],
            recipient=email['recipient'],
            body=email['body'],
            html_body=email.get('html_body'),
            received_date=datetime.fromisoformat(email['received_date']) if isinstance(email['received_date'], str) else email['received_date'],
            has_attachments=email['has_attachments'],
            is_read=email['is_read'],
            labels=[]
        )

        # Check if summary exists in cache
        if email.get('summary'):
            print_info("Using cached summary")
            print_summary(email['summary'], email.get('action_items'))
        else:
            print_info("Generating summary with Claude...")
            result = summarizer.summarize(email_obj)

            # Cache the summary
            cache.update_summary(email['id'], result['summary'], result.get('action_items'))

            print_summary(result['summary'], result.get('action_items'))

    except Exception as e:
        print_error(f"Summarization failed: {e}")
        logger.error(f"Summarization error: {e}", exc_info=True)

    finally:
        cache.close()

@cli.command()
@click.argument('query')
@click.option('--limit', default=20, help='Maximum results to return')
@click.pass_context
def search(ctx, query: str, limit: int):
    """Search emails using natural language."""
    profile = ctx.obj.get('profile')
    config = get_config(profile)
    cache = EmailCache(config['database'].path)
    searcher = EmailSearcher()

    try:
        print_info(f"Searching for: '{query}'")

        # Parse natural language query
        search_params = searcher.parse_search_query(query)

        print_info("Search parameters extracted")

        # Build and execute SQL query
        sql_query, params = searcher.build_sql_query(search_params)

        cursor = cache.connection.cursor()
        cursor.execute(sql_query, params)
        results = [dict(row) for row in cursor.fetchall()]

        if not results:
            print_warning("No emails found matching your query")
            return

        print_info(f"Found {len(results)} results")

        # Rank results
        if len(results) > 1:
            print_info("Ranking results by relevance...")
            results = searcher.rank_results(results, query)

        # Display results
        print_email_table(results[:limit], show_category=True)

    except Exception as e:
        print_error(f"Search failed: {e}")
        logger.error(f"Search error: {e}", exc_info=True)

    finally:
        cache.close()

@cli.command()
@click.option('--limit', default=100, help='Maximum emails to categorize')
@click.pass_context
def categorize_all(ctx, limit: int):
    """Categorize all uncategorized emails."""
    profile = ctx.obj.get('profile')
    config = get_config(profile)
    cache = EmailCache(config['database'].path)
    categorizer = EmailCategorizer()

    try:
        # Get uncategorized emails
        all_emails = cache.get_emails(limit=limit)
        uncategorized = [e for e in all_emails if not e.get('category')]

        if not uncategorized:
            print_info("All emails are already categorized")
            return

        print_info(f"Categorizing {len(uncategorized)} emails...")

        from providers.base import Email
        from datetime import datetime

        for i, email_data in enumerate(uncategorized, 1):
            try:
                # Convert to Email object
                email_obj = Email(
                    id=email_data['id'],
                    subject=email_data['subject'],
                    sender=email_data['sender'],
                    recipient=email_data['recipient'],
                    body=email_data['body'],
                    html_body=email_data.get('html_body'),
                    received_date=datetime.fromisoformat(email_data['received_date']) if isinstance(email_data['received_date'], str) else email_data['received_date'],
                    has_attachments=email_data['has_attachments'],
                    is_read=email_data['is_read'],
                    labels=[]
                )

                # Categorize
                result = categorizer.categorize(email_obj)

                # Update cache
                cache.update_category(
                    email_data['id'],
                    result['category'],
                    result['reasoning']
                )

                print_info(f"[{i}/{len(uncategorized)}] Categorized: {email_data['subject'][:50]}... → {result['category']}")

            except Exception as e:
                print_error(f"Failed to categorize email {email_data['id']}: {e}")

        print_success(f"Categorization complete! Processed {len(uncategorized)} emails")

    except Exception as e:
        print_error(f"Categorization failed: {e}")
        logger.error(f"Categorization error: {e}", exc_info=True)

    finally:
        cache.close()

@cli.command()
@click.pass_context
def stats(ctx):
    """Display email statistics."""
    profile = ctx.obj.get('profile')
    config = get_config(profile)
    cache = EmailCache(config['database'].path)

    try:
        if profile:
            print_info(f"Statistics for profile: {profile}")
        statistics = cache.get_statistics()
        print_statistics(statistics)

    finally:
        cache.close()

@cli.command()
@click.option('--days', default=None, type=int, help='Days to keep (default from config)')
@click.pass_context
def clean(ctx, days: Optional[int]):
    """Clean old emails from cache."""
    profile = ctx.obj.get('profile')
    config = get_config(profile)
    cache = EmailCache(config['database'].path)

    try:
        deleted = cache.clean_old_emails(days)
        print_success(f"Cleaned {deleted} old emails from cache")

    finally:
        cache.close()

if __name__ == '__main__':
    cli()
