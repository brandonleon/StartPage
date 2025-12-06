StartPage is a self-hosted, frecency-based link manager designed to serve as your browser's start page. Links are dynamically ranked using a weighted algorithm that combines frequency and recency of access.

## Features

- **Frecency-based ranking** - Links are automatically ordered by a combination of access frequency and recency
- **Tag organization** - Add tags to links for better categorization and filtering
- **Dark/light theme** - Toggle between mocha (dark) and latte (light) themes
- **Search functionality** - Real-time search with HTMX-powered dynamic loading
- **Dashboard monitoring** - View link health and manage low-rank items before automatic cleanup
- **Docker support** - Easy deployment with persistent storage
- **FastAPI backend** - Modern async Python web framework with SQLite storage

### How Frecency Works

Frecency is a portmanteau of 'recent' and 'frequency'. It's a weighted rank that depends on how often and how recently something occurred (term coined by Mozilla).

The algorithm ensures that:
- A link with low rank but recent access quickly rises above frequently-accessed but stale links
- Links below rank 1.0 become eligible for automatic cleanup
- When total rank sum exceeds 1000, ranks are reduced by 1% to prevent overflow
## Installation

### Docker Installation (recommended)
1. Clone this repository
   ```shell
   git clone https://github.com/yourusername/startpage.git
   cd startpage
   ```

2. Build and run with Docker
   ```shell
   docker build . -t startpage
   docker run -d -p 8080:8080 --restart=always --name startpage \
     -v ~/.config/startpage:/usr/startpage/data startpage
   ```

   Or use the Makefile:
   ```shell
   make dockerbuild
   ```

### Development Installation
1. Install [uv](https://github.com/astral-sh/uv)
   ```shell
   pipx install uv
   ```

2. Clone and install dependencies
   ```shell
   git clone https://github.com/yourusername/startpage.git
   cd startpage
   uv sync
   ```

3. Start the development server
   ```shell
   make develop
   # or
   uv run uvicorn main:app --reload
   ```

## Usage

### Adding Links
- Navigate to `/add` or click "Add" in the navbar
- Enter a name and URL
- Optionally add comma-separated tags (e.g., `work, documentation, python`)
- Links are assigned the average rank on creation to naturally find their position

### Managing Tags
- **Add tags**: Include them when creating/editing links in the tag field
- **View all tags**: Visit `/tags` to see all tags and their usage counts
- **Filter by tag**: Click a tag to view all associated links
- **Remove tags**: Edit a link and click the × on any tag badge

### Search and Browse
- Use the navbar search for instant filtering (HTMX-powered)
- Click any link to visit it (automatically increments rank)
- View `/dashboard` to see links grouped by health status
- Check `/stats` for database statistics

### Theme Switching
Click the theme toggle in the navbar to switch between dark (mocha) and light (latte) modes. Theme preference is stored in localStorage.
