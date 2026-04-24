"""Display formatting utilities using Rich library."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from datetime import datetime
from typing import List, Dict, Any, Optional

console = Console()

CATEGORY_COLORS = {
    'urgent': 'red',
    'important': 'yellow',
    'newsletter': 'blue',
    'receipts': 'green',
    'social': 'magenta',
    'can_wait': 'dim'
}

CATEGORY_ICONS = {
    'urgent': '🔴',
    'important': '🟡',
    'newsletter': '📰',
    'receipts': '🧾',
    'social': '💬',
    'can_wait': '⏸️'
}

def print_email_table(emails: List[Dict[str, Any]], show_category: bool = True) -> None:
    """
    Display emails in a formatted table.

    Args:
        emails: List of email dictionaries
        show_category: Whether to show category column
    """
    if not emails:
        console.print("[yellow]No emails found[/yellow]")
        return

    table = Table(show_header=True, header_style="bold magenta")

    table.add_column("#", style="dim", width=4)
    table.add_column("Date", style="cyan", width=12)
    table.add_column("From", style="green", width=25)
    table.add_column("Subject", width=50)

    if show_category:
        table.add_column("Category", width=12)

    table.add_column("Status", width=8)

    for i, email in enumerate(emails, 1):
        # Format date
        try:
            date_obj = email['received_date']
            if isinstance(date_obj, str):
                date_obj = datetime.fromisoformat(date_obj)
            date_str = date_obj.strftime('%Y-%m-%d')
        except:
            date_str = 'Unknown'

        # Format sender (truncate if too long)
        sender = email['sender'][:23] + '...' if len(email['sender']) > 25 else email['sender']

        # Format subject
        subject = email['subject'][:48] + '...' if len(email['subject']) > 50 else email['subject']

        # Status icon
        status = '📖' if email['is_read'] else '✉️'

        row = [
            str(i),
            date_str,
            sender,
            subject
        ]

        if show_category:
            category = email.get('category', 'can_wait')
            icon = CATEGORY_ICONS.get(category, '⏸️')
            color = CATEGORY_COLORS.get(category, 'white')
            category_text = f"[{color}]{icon} {category}[/{color}]"
            row.append(category_text)

        row.append(status)

        table.add_row(*row)

    console.print(table)
    console.print(f"\n[dim]Total: {len(emails)} emails[/dim]")

def print_email_detail(email: Dict[str, Any], summary: Optional[str] = None) -> None:
    """
    Display detailed view of a single email.

    Args:
        email: Email dictionary
        summary: Optional AI-generated summary
    """
    # Header
    console.print(f"\n[bold cyan]Email Details[/bold cyan]")
    console.print("=" * 80)

    # Basic info
    console.print(f"[bold]Subject:[/bold] {email['subject']}")
    console.print(f"[bold]From:[/bold] {email['sender']}")
    console.print(f"[bold]To:[/bold] {email['recipient']}")

    # Date
    try:
        date_obj = email['received_date']
        if isinstance(date_obj, str):
            date_obj = datetime.fromisoformat(date_obj)
        date_str = date_obj.strftime('%Y-%m-%d %H:%M:%S')
    except:
        date_str = 'Unknown'

    console.print(f"[bold]Date:[/bold] {date_str}")

    # Category
    if email.get('category'):
        category = email['category']
        icon = CATEGORY_ICONS.get(category, '⏸️')
        color = CATEGORY_COLORS.get(category, 'white')
        console.print(f"[bold]Category:[/bold] [{color}]{icon} {category}[/{color}]")

    # Status
    status_text = 'Read 📖' if email['is_read'] else 'Unread ✉️'
    console.print(f"[bold]Status:[/bold] {status_text}")

    # Summary (if provided)
    if summary:
        console.print(f"\n[bold yellow]AI Summary:[/bold yellow]")
        summary_panel = Panel(
            Markdown(summary),
            title="Summary",
            border_style="yellow"
        )
        console.print(summary_panel)

    # Body
    console.print(f"\n[bold]Email Body:[/bold]")
    body_text = email.get('body', 'No content')
    body_panel = Panel(
        body_text[:2000] + ('...' if len(body_text) > 2000 else ''),
        title="Content",
        border_style="blue"
    )
    console.print(body_panel)

    console.print("=" * 80 + "\n")

def print_summary(summary_text: str, action_items: Optional[str] = None) -> None:
    """
    Display email summary in a formatted panel.

    Args:
        summary_text: Summary text
        action_items: Optional action items
    """
    console.print("\n[bold cyan]Email Summary[/bold cyan]")

    # Summary panel
    summary_panel = Panel(
        Markdown(summary_text),
        title="Summary",
        border_style="cyan"
    )
    console.print(summary_panel)

    # Action items panel
    if action_items and action_items.lower() != 'none':
        action_panel = Panel(
            Markdown(action_items),
            title="Action Items",
            border_style="yellow"
        )
        console.print(action_panel)

def print_statistics(stats: Dict[str, Any]) -> None:
    """
    Display email statistics.

    Args:
        stats: Statistics dictionary
    """
    console.print("\n[bold cyan]Email Statistics[/bold cyan]")
    console.print("=" * 80)

    # Total emails
    console.print(f"[bold]Total Emails:[/bold] {stats.get('total_emails', 0)}")
    console.print(f"[bold]Unread Emails:[/bold] {stats.get('unread_emails', 0)}")

    # By category
    if 'by_category' in stats and stats['by_category']:
        console.print(f"\n[bold]By Category:[/bold]")
        for category, count in stats['by_category'].items():
            icon = CATEGORY_ICONS.get(category, '⏸️')
            color = CATEGORY_COLORS.get(category, 'white')
            console.print(f"  [{color}]{icon} {category}: {count}[/{color}]")

    # By provider
    if 'by_provider' in stats and stats['by_provider']:
        console.print(f"\n[bold]By Provider:[/bold]")
        for provider, count in stats['by_provider'].items():
            console.print(f"  • {provider}: {count}")

    console.print("=" * 80 + "\n")

def print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[bold green]✓ {message}[/bold green]")

def print_error(message: str) -> None:
    """Print error message."""
    console.print(f"[bold red]✗ {message}[/bold red]")

def print_info(message: str) -> None:
    """Print info message."""
    console.print(f"[bold blue]ℹ {message}[/bold blue]")

def print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[bold yellow]⚠ {message}[/bold yellow]")

def confirm(message: str) -> bool:
    """
    Ask user for confirmation.

    Args:
        message: Confirmation message

    Returns:
        True if user confirms, False otherwise
    """
    from rich.prompt import Confirm
    return Confirm.ask(message)
