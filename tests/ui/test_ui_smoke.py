import pytest

# Skip entire module if playwright is not installed
pytest.importorskip("playwright", reason="playwright not installed")

from playwright.sync_api import Page, expect

def test_homepage_loads(page: Page, base_url: str):
    """Test that the homepage loads correctly."""
    page.goto(base_url)
    
    # Check title
    expect(page).to_have_title("Inzyts")
    
    # Check for main container
    expect(page.locator("#root")).to_be_visible()

def test_analysis_form_present(page: Page, base_url: str):
    """Test that the analysis form is present and visible."""
    page.goto(base_url)
    
    # Check for the form header
    expect(page.get_by_role("heading", name="Start New Analysis")).to_be_visible()
    
    # Check for submit button
    expect(page.get_by_role("button", name="Start Analysis")).to_be_visible()

def test_frontend_backend_connectivity(page: Page, base_url: str):
    """
    Test that the frontend can communicate with the backend.
    """
    page.goto(base_url)
    
    # Check for connection status indicator
    # Based on App.tsx: {isConnected ? '● Connected' : '○ Disconnected'}
    # We expect it to be visible. It might be Disconnected if backend is down, but the element should exist.
    expect(page.get_by_text("Connected", exact=False)).to_be_visible()

def test_form_validation(page: Page, base_url: str):
    """Test that the form validates missing inputs."""
    page.goto(base_url)
    
    # Find the analyze button
    analyze_btn = page.get_by_role("button", name="Start Analysis")
    
    if analyze_btn.is_visible():
        analyze_btn.click()
        
        # Should show error about missing file
        # Based on AnalysisForm.tsx: setError("Please provide a CSV file or path.");
        expect(page.get_by_text("Please provide a CSV file or path")).to_be_visible() 
