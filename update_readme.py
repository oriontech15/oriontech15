import requests
import datetime
import re
import os
import logging
import traceback

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('update_readme.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "oriontech15")  # Reads from env, falls back to hardcoded
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # Reads from env, or None if not set

START_MARKER = "<!-- GITHUB_SUMMARY_START -->"
END_MARKER = "<!-- GITHUB_SUMMARY_END -->"

def fetch_yearly_events(username, token=None):
    """Fetch GitHub events for the current year with error handling."""
    try:
        logger.info(f"Starting to fetch events for user: {username}")
        headers = {"Authorization": f"token {token}"} if token else {}
        events = []
        page = 1
        this_year = datetime.datetime.now().year
        logger.info(f"Fetching events for year: {this_year}")

        while True:
            try:
                url = f"https://api.github.com/users/{username}/events/public?page={page}&per_page=100"
                logger.info(f"Fetching page {page} from: {url}")
                
                resp = requests.get(url, headers=headers, timeout=30)
                logger.info(f"Response status code: {resp.status_code}")
                
                if resp.status_code != 200:
                    error_msg = f"GitHub API returned status {resp.status_code}"
                    if resp.status_code == 404:
                        error_msg += f" - User '{username}' not found"
                    elif resp.status_code == 403:
                        error_msg += " - Rate limit exceeded or authentication failed"
                    logger.error(error_msg)
                    logger.error(f"Response content: {resp.text}")
                    return []
                
                data = resp.json()
                if not data:
                    logger.info("No more data received from API")
                    break
                
                page_events = 0
                for event in data:
                    try:
                        event_year = datetime.datetime.strptime(event["created_at"], "%Y-%m-%dT%H:%M:%SZ").year
                        if event_year == this_year:
                            events.append(event)
                            page_events += 1
                    except (KeyError, ValueError) as e:
                        logger.warning(f"Error parsing event date on line {traceback.extract_stack()[-1].lineno}: {e}")
                        logger.warning(f"Event data: {event}")
                        continue
                
                logger.info(f"Found {page_events} events from this year on page {page}")
                
                # Check if we've gone past this year
                if any(datetime.datetime.strptime(e["created_at"], "%Y-%m-%dT%H:%M:%SZ").year < this_year for e in data):
                    logger.info("Reached events from previous year, stopping pagination")
                    break
                page += 1
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error on line {traceback.extract_stack()[-1].lineno}: {e}")
                return []
            except Exception as e:
                logger.error(f"Unexpected error in fetch_yearly_events on line {traceback.extract_stack()[-1].lineno}: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return []
        
        logger.info(f"Successfully fetched {len(events)} events for {username}")
        return events
        
    except Exception as e:
        logger.error(f"Critical error in fetch_yearly_events on line {traceback.extract_stack()[-1].lineno}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return []

def summarize_events(events):
    """Summarize events with error handling."""
    try:
        logger.info("Starting to summarize events")
        repos = set()
        
        for event in events:
            try:
                repo_name = event["repo"]["name"]
                repos.add(repo_name)
            except (KeyError, TypeError) as e:
                logger.warning(f"Error extracting repo name on line {traceback.extract_stack()[-1].lineno}: {e}")
                logger.warning(f"Event data: {event}")
                continue
        
        summary = {
            "total_events": len(events),
            "unique_repos": len(repos),
            "repos": repos
        }
        
        logger.info(f"Summary created: {summary['total_events']} events, {summary['unique_repos']} repos")
        return summary
        
    except Exception as e:
        logger.error(f"Error in summarize_events on line {traceback.extract_stack()[-1].lineno}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "total_events": 0,
            "unique_repos": 0,
            "repos": set()
        }

def generate_summary_text(summary):
    """Generate summary text with error handling."""
    try:
        logger.info("Generating summary text")
        lines = [
            f"**Total public events this year:** {summary['total_events']}",
            f"**Repositories contributed to:** {summary['unique_repos']}",
            "## Repositories:"
        ]
        
        if summary["repos"]:
            lines += [f"- {repo}" for repo in sorted(summary["repos"])]
        else:
            lines.append("- No repositories found")
        
        summary_text = "\n".join(lines)
        logger.info("Summary text generated successfully")
        return summary_text
        
    except Exception as e:
        logger.error(f"Error in generate_summary_text on line {traceback.extract_stack()[-1].lineno}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return "**Error generating summary**"

def update_readme(summary, readme_path="README.md"):
    """Update README with error handling."""
    try:
        logger.info(f"Starting to update README: {readme_path}")
        
        # Check if file exists
        if not os.path.exists(readme_path):
            logger.warning(f"README file not found: {readme_path}")
            logger.info("Creating new README file")
            content = ""
        else:
            try:
                with open(readme_path, "r", encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"Successfully read existing README ({len(content)} characters)")
            except UnicodeDecodeError as e:
                logger.error(f"Unicode decode error on line {traceback.extract_stack()[-1].lineno}: {e}")
                # Try with different encoding
                try:
                    with open(readme_path, "r", encoding='latin-1') as f:
                        content = f.read()
                    logger.info("Successfully read README with latin-1 encoding")
                except Exception as e2:
                    logger.error(f"Failed to read README with alternative encoding on line {traceback.extract_stack()[-1].lineno}: {e2}")
                    content = ""
            except Exception as e:
                logger.error(f"Error reading README on line {traceback.extract_stack()[-1].lineno}: {e}")
                content = ""

        summary_text = generate_summary_text(summary)
        pattern = re.compile(
            f"{START_MARKER}.*?{END_MARKER}", re.DOTALL
        )
        replacement = f"{START_MARKER}\n{summary_text}\n{END_MARKER}"

        if pattern.search(content):
            logger.info("Found existing markers, updating content")
            new_content = pattern.sub(replacement, content)
        else:
            logger.info("No markers found, appending to end")
            new_content = content + f"\n\n{replacement}"

        try:
            with open(readme_path, "w", encoding='utf-8') as f:
                f.write(new_content)
            logger.info(f"Successfully wrote updated README ({len(new_content)} characters)")
        except Exception as e:
            logger.error(f"Error writing README on line {traceback.extract_stack()[-1].lineno}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
            
    except Exception as e:
        logger.error(f"Critical error in update_readme on line {traceback.extract_stack()[-1].lineno}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

if __name__ == "__main__":
    try:
        logger.info("=== Starting README update process ===")
        logger.info(f"GitHub username: {GITHUB_USERNAME}")
        logger.info(f"GitHub token provided: {'Yes' if GITHUB_TOKEN else 'No'}")
        
        events = fetch_yearly_events(GITHUB_USERNAME, GITHUB_TOKEN)
        if not events:
            logger.warning("No events fetched, but continuing with empty summary")
        
        summary = summarize_events(events)
        update_readme(summary)
        
        logger.info("=== README update completed successfully ===")
        print("README.md updated with yearly summary section!")
        
    except Exception as e:
        logger.error(f"Critical error in main execution on line {traceback.extract_stack()[-1].lineno}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(f"Error updating README: {e}")
        print("Check update_readme.log for detailed error information.")
        exit(1)
