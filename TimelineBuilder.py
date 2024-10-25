import os
import pandas as pd
import plotly.figure_factory as ff
import plotly.graph_objects as go
import plotly.graph_objects as golist
import requests
import re
import json
from dotenv import load_dotenv
from datetime import datetime
from dateutil import parser
import plotly.io as pio
import sys

# Set the renderer to open the plot in a web browser
pio.renderers.default = "browser"

# Load environment variables from .env file
load_dotenv()
API_URL = "https://api.openai.com/v1/chat/completions"
API_KEY = ("INSERT API KEY")

# Request timeout duration
TIMEOUT_SECONDS = 30

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer [INSERT API KEY] "
}
def parse_date(date_str):
    """
    Enhanced date parsing to correctly handle historical dates and date ranges.
    """
    try:
        date_str = date_str.strip()
        if not date_str:
            return None

        # Debugging: Print the original date string
        print(f"Attempting to parse: '{date_str}'")

        # Check if the string is a range (e.g., "July 19-20, 1848")
        range_match = re.match(r'(\w+ \d+)-\d+, \d+', date_str)
        if range_match:
            # If it's a range, extract just the first date (e.g., "July 19, 1848")
            first_date_str = range_match.group(1) + date_str[date_str.rfind(","):]
            parsed_date = parser.parse(first_date_str, fuzzy=True)
        else:
            parsed_date = parser.parse(date_str, fuzzy=True)

        # Debugging: Show the parsed date result
        print(f"Parsed date result: '{parsed_date}'")

        # Check if parsed year is in the future, which might indicate an issue
        if parsed_date.year > datetime.now().year:
            print("Parsed year is in the future, potential misinterpretation.")
            return None

        return pd.Timestamp(parsed_date)

    except Exception as e:
        print(f"Warning: Failed to parse date '{date_str}': {str(e)}")
        return None

def fetch_events_from_openai(prompt):
    try:
        system_prompt = """
        Please provide a list of historical events in the following format EXACTLY:
        
        Event: [Event Description]
        Date: [Date]
        Category: [Category/Stream name]
        """

        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }

        print("\n=== Sending Request to OpenAI ===")
        response = requests.post(API_URL, headers=headers, data=json.dumps(data), timeout=TIMEOUT_SECONDS)
        
        if response.status_code != 200:
            print(f"Error: OpenAI API returned status code {response.status_code}")
            print(f"Response: {response.text}")
            return []

        response_data = response.json()
        
        if not response_data.get("choices") or not response_data["choices"][0].get("message"):
            print("No valid response from OpenAI.")
            return []

        response_content = response_data["choices"][0]["message"]["content"].strip()
        
        # Split into event blocks
        event_blocks = re.split(r'\n\s*\n', response_content)
        
        events = []
        for block in event_blocks:
            if not block.strip():
                continue

            event_data = {}
            
            # Extract event description
            event_match = re.search(r'Event:\s*(.+)', block, re.IGNORECASE)
            if event_match:
                event_data['Task'] = event_match.group(1).strip()

            # Extract date
            date_match = re.search(r'Date:\s*(.+)', block, re.IGNORECASE)
            if date_match:
                event_date = parse_date(date_match.group(1).strip())
                if event_date:
                    event_data['Date'] = event_date

            # Extract category
            category_match = re.search(r'Category:\s*(.+)', block, re.IGNORECASE)
            if category_match:
                event_data['Category'] = category_match.group(1).strip()

            if all(k in event_data for k in ['Task', 'Date', 'Category']):
                events.append(event_data)

        return events

    except requests.Timeout:
        print("Error: Request to OpenAI API timed out")
        return []
    except Exception as e:
        print(f"Error in fetch_events_from_openai: {str(e)}")
        return []

def truncate_text(text, max_length=50):
    """
    Truncate text to a maximum length and add ellipses if needed.
    """
    return text if len(text) <= max_length else text[:max_length] + '...'

def create_timeline_plot(event_data):
    """
    Create a timeline plot where each event is marked as a point on the x-axis (date).
    """
    try:
        if not event_data:
            print("Error: No event data provided")
            return None

        print("Creating Timeline plot...")
        df = pd.DataFrame(event_data)

        # Print the DataFrame
        print(df)

        # Save the DataFrame to a CSV file
        df.to_csv("event_data.csv", index=False)

        # Create the scatter plot with some adjustments
        y_positions = [i % 2 for i in range(len(df))]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=y_positions,
            mode='markers+text',
            text=[truncate_text(task) for task in df['Task']],
            textposition='top right',
            hovertext=df['Task'],
            hoverinfo='text',
            marker=dict(
                symbol='circle',
                size=10,
                color='rgb(51, 133, 255)'
            )
        ))

        # Update layout
        fig.update_layout(
            title='Timeline of Historical Events',
            showlegend=False,
            xaxis=dict(
                title='Date',
                showgrid=True,
                tickangle=-45
            ),
            yaxis=dict(
                showticklabels=False,
                showgrid=False
            ),
            height=600,
            width=2000
        )

        fig.show()

        return fig

    except Exception as e:
        print(f"Error creating timeline plot: {str(e)}")
        return None

if __name__ == "__main__":
    if not API_KEY:
        print("Error: No API key found. Please set your OpenAI API key in the .env file.")
        sys.exit(1)

    try:
        user_prompt = input("Enter a prompt to request historical events (e.g., 'List significant events in women's history in the USA'): ").strip()
        print("\n=== Starting Event Generation ===")
        
        event_data = fetch_events_from_openai(user_prompt)

        if event_data:
            print(f"\nFound {len(event_data)} events")
            create_timeline_plot(event_data)
        else:
            print("No events were found. Please try again with a different prompt.")
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        sys.exit(1)