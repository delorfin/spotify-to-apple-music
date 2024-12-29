from sys import argv
import sys
import csv
import urllib.parse, urllib.request
import json
from time import sleep
import requests
import os
import sys
import time
import platform
from tqdm import tqdm
import re
from datetime import datetime
from difflib import SequenceMatcher
import html

if platform.system() == 'Darwin':  # macOS
    try:
        import caffeine
        caffeine_enabled = True
    except ImportError:
        print("Note: Install 'caffeine' package to prevent sleep during processing:")
        print("pip install caffeine")
        caffeine_enabled = False
else:
    caffeine_enabled = False

# Delay (in seconds) to wait between tracks
delay = 1

# Checking if the command is correct
if len(argv) > 1 and argv[1]:
    pass
else:
    print('\nCommand usage:\npython3 convert.py yourplaylist.csv\nMore info at https://github.com/delorfin/spotify-to-apple-music')
    exit()

class MatchResult:
    def __init__(self, track_id=None, confidence=0, match_method=None, alternative_matches=None):
        self.track_id = track_id
        self.confidence = confidence
        self.match_method = match_method
        self.alternative_matches = alternative_matches or []

def get_connection_data(f, prompt):
    """Get connection data from file or user input"""
    if os.path.exists(f):
        with open(f, 'r') as file:
            return file.read().rstrip('\n')
    else:
        return input(prompt)

def clean_string(s):
    """Enhanced string cleaning with additional music-specific normalizations"""
    if not s:
        return ""
    # Convert to lowercase and remove special characters
    s = re.sub(r'[^\w\s]', ' ', s.lower())
    
    # Remove common additions
    removals = [
        r'\b(official\s+)?(music\s+)?video\b',
        r'\b(official\s+)?(audio)\b',
        r'\b(official\s+)?(lyric\s+video)\b',
        r'\bofficial\b',
        r'\blyrics\b',
        r'\bremix\b',
        r'\bver(\.|sion)?\b',
        r'\bremaster(ed)?\b'
    ]
    for pattern in removals:
        s = re.sub(pattern, '', s, flags=re.IGNORECASE)
    
    # Normalize whitespace
    return ' '.join(s.split())

def remove_features(title):
    """Remove featuring artists with enhanced pattern matching"""
    if not title:
        return ""
    patterns = [
        r'\(feat\..*?\)',
        r'\(ft\..*?\)',
        r'\(featuring.*?\)',
        r'\(with.*?\)',
        r'\bfeat\..*?(?=\s|$|\()',
        r'\bft\..*?(?=\s|$|\()',
        r'\bfeaturing.*?(?=\s|$|\()',
        r'\bwith\s+(?:[^()]+)(?=\s|$|\()'
    ]
    for pattern in patterns:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)
    return title.strip()

def get_string_similarity(str1, str2):
    """Calculate similarity between two strings"""
    # Handle None values
    if not str1 or not str2:
        return 0
    return SequenceMatcher(None, clean_string(str1), clean_string(str2)).ratio()

def create_apple_music_playlist(session, playlist_name):
    """Create a new playlist in Apple Music"""
    url = "https://amp-api.music.apple.com/v1/me/library/playlists"
    data = {
        'attributes': {
            'name': playlist_name,
            'description': 'A new playlist created via API using Spotify-2-AppleMusic',
        }
    }
    
    # Test if playlist exists and create it if not
    response = session.get(url)
    if response.status_code == 200:
        for playlist in response.json()['data']:
            if playlist['attributes']['name'] == playlist_name:
                print(f"Playlist {playlist_name} already exists!")
                return playlist['id']
    
    response = session.post(url, json=data)
    if response.status_code == 201:
        sleep(0.2)
        return response.json()['data'][0]['id']
    elif response.status_code == 401:
        print("\nError 401: Unauthorized. Please refer to the README and check you have entered your Bearer Token, Media-User-Token and session cookies.\n")
        sys.exit(1)
    elif response.status_code == 403:
        print("\nError 403: Forbidden. Please refer to the README and check you have entered your Bearer Token, Media-User-Token and session cookies.\n")
        sys.exit(1)
    else:
        raise Exception(f"Error {response.status_code} while creating playlist {playlist_name}!")
        sys.exit(1)

def like_track(session, song_id):
    """Function to like/rate a track in Apple Music"""
    url = f"https://amp-api.music.apple.com/v1/me/ratings/songs/{song_id}"
    data = {
        "type": "rating",
        "attributes": {
            "value": 1
        }
    }
    try:
        response = session.put(url, json=data)
        return "OK" if response.status_code in [200, 201, 204] else "ERROR"
    except Exception:
        return "ERROR"

def get_track_details(track_id, session):
    """Get detailed track information from Apple Music"""
    try:
        url = f"https://amp-api.music.apple.com/v1/catalog/{country_code}/songs/{track_id}"
        response = session.get(url)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']:
                track = data['data'][0]['attributes']
                return {
                    'id': track_id,
                    'name': track['name'],
                    'artist': track['artistName'],
                    'album': track['albumName'],
                    'preview_url': track.get('previews', [{}])[0].get('url'),
                    'artwork_url': track.get('artwork', {}).get('url'),
                    'release_date': track.get('releaseDate')
                }
    except Exception as e:
        print(f"Error getting track details: {e}")
    return None

def write_error_report(filename, failed_tracks):
    """Write a detailed HTML error report for failed tracks with country-specific links"""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Failed Tracks Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .track {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .track:hover {{ background-color: #f5f5f5; }}
            .search-link {{ color: #0066cc; text-decoration: none; margin-right: 15px; }}
            .search-link:hover {{ text-decoration: underline; }}
            .confidence {{ color: #666; font-size: 0.9em; }}
            .alternative {{ margin-left: 20px; padding: 10px; background-color: #f8f8f8; }}
            .button-group {{ margin-top: 10px; }}
        </style>
        <script>
            function openInApp(url) {{
                // Convert web URL to Apple Music app URL
                let appUrl = url.replace('https://music.apple.com', 'music:');
                window.location.href = appUrl;
                
                // Fallback to web version after a short delay if app doesn't open
                setTimeout(function() {{
                    window.location.href = url;
                }}, 1000);
            }}
        </script>
    </head>
    <body>
        <h1>Failed Tracks Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}</h1>
        <p>The following tracks could not be automatically matched. Click the search links to find them manually in Apple Music.</p>
    """
    
    for track in failed_tracks:
        # Create search links for different combinations
        title_artist = urllib.parse.quote(f"{track['title']} {track['artist']}")
        title_only = urllib.parse.quote(track['title'])
        
        html_content += f"""
        <div class="track">
            <h3>{html.escape(track['title'])}</h3>
            <p>Artist: {html.escape(track['artist'])}<br>
            Album: {html.escape(track['album'])}<br>
            ISRC: {track['isrc']}</p>
            
            <div class="button-group">
                <button onclick="openInApp('https://music.apple.com/{country_code}/search?term={title_artist}')" class="search-link">
                    Search Title + Artist in App
                </button>
                <button onclick="openInApp('https://music.apple.com/{country_code}/search?term={title_only}')" class="search-link">
                    Search Title Only in App
                </button>
                <a href="https://music.apple.com/{country_code}/search?term={title_artist}" target="_blank" class="search-link">
                    Open in Browser
                </a>
            </div>
        """
        
        if track.get('alternatives'):
            html_content += '<div class="alternative"><p>Possible matches (but below confidence threshold):</p><ul>'
            for alt in track['alternatives']:
                html_content += f"""
                <li>{html.escape(alt['name'])} by {html.escape(alt['artist'])} 
                    (Confidence: {alt['confidence']:.2f})<br>
                    <button onclick="openInApp('https://music.apple.com/{country_code}/song/{alt['id']}')" class="search-link">
                        Open in App
                    </button>
                    <a href="https://music.apple.com/{country_code}/song/{alt['id']}" target="_blank" class="search-link">
                        Open in Browser
                    </a>
                </li>"""
            html_content += '</ul></div>'
        
        html_content += '</div>'
    
    html_content += """
    </body>
    </html>
    """
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

def add_to_library(session, song_id):
    """Add a song to the user's Apple Music library"""
    url = "https://amp-api.music.apple.com/v1/me/library"
    data = {
        "data": [{
            "id": str(song_id),
            "type": "songs"
        }]
    }
    
    try:
        response = session.post(url, json=data)
        return "OK" if response.status_code in [200, 201, 204] else "ERROR"
    except Exception:
        return "ERROR"

def process_songs(file, mode='playlist'):
    """Process songs with support for library mode"""
    failed_tracks = []
    
    # Prevent sleep on macOS if possible
    if caffeine_enabled:
        caffeine.on(display=True)
    
    try:
        with requests.Session() as s:
            s.headers.update({
                "Authorization": f"{token}",
                "media-user-token": f"{media_user_token}",
                "Cookie": f"{cookies}".encode('utf-8'),
                "Host": "amp-api.music.apple.com",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://music.apple.com/",
                "Origin": "https://music.apple.com",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
            })
            
            playlist_identifier = None
            playlist_track_ids = []
            playlist_name = None
            
            if mode == 'playlist':
                playlist_name = os.path.basename(file).split('.')[0].replace('_', ' ').capitalize()
                playlist_identifier = create_apple_music_playlist(s, playlist_name)
                playlist_track_ids = get_playlist_track_ids(s, playlist_identifier)
            
            # Count total tracks first
            with open(str(file), encoding='utf-8') as csvfile:
                total_tracks = sum(1 for row in csv.reader(csvfile)) - 1  # Subtract header row
            
            # Initialize progress bar
            progress = tqdm(
                total=total_tracks,
                desc="Processing tracks",
                unit="track",
                bar_format='{desc}: {percentage:3.0f}% |{bar}| {n_fmt}/{total_fmt} (Time remaining: {remaining})'
            )
            
            matched = 0
            failed = 0
            
            with open(str(file), encoding='utf-8') as csvfile:
                file_reader = csv.reader(csvfile)
                header_row = next(file_reader)
                
                if header_row[1] != 'Track Name' or header_row[3] != 'Artist Name(s)' or header_row[5] != 'Album Name' or header_row[16] != 'ISRC':
                    print('\nThe CSV file is not in the correct format!\nPlease be sure to download the CSV file(s) only from https://watsonbox.github.io/exportify/.\n\n')
                    return
                
                for row in file_reader:
                    title, artist, album, album_artist, isrc = [clean_string(x) for x in [row[1], row[3], row[5], row[7], row[16]]]
                    
                    # Update progress description
                    progress.set_description(f"Processing {title[:30]}{'...' if len(title) > 30 else ''}")
                    
                    # Try ISRC first
                    track_id = None
                    if isrc:
                        track_id = match_isrc_to_itunes_id(s, album, album_artist, isrc)
                    
                    # If ISRC fails, try text search
                    if not track_id:
                        match_result = get_itunes_id(title, artist, album, s)
                        if match_result.track_id:
                            track_id = match_result.track_id
                    
                    if track_id:
                        if mode == 'playlist':
                            result = add_song_to_playlist(s, track_id, playlist_identifier, playlist_track_ids, playlist_name)
                        elif mode == 'like':
                            result = like_track(s, track_id)
                        else:  # library mode
                            result = add_to_library(s, track_id)
                            
                        if result == "OK":
                            matched += 1
                        else:
                            failed += 1
                            failed_tracks.append({
                                'title': title,
                                'artist': artist,
                                'album': album,
                                'isrc': isrc,
                                'error': 'Failed to process'
                            })
                    else:
                        failed += 1
                        failed_tracks.append({
                            'title': title,
                            'artist': artist,
                            'album': album,
                            'isrc': isrc,
                            'alternatives': match_result.alternative_matches if 'match_result' in locals() else []
                        })
                    
                    progress.update(1)
                    sleep(delay)
            
            progress.close()
            
            # Generate report
            success_rate = (matched / total_tracks) * 100 if total_tracks > 0 else 0
            print(f"\n=== Processing Complete ===")
            print(f"Total tracks: {total_tracks}")
            print(f"Successfully processed: {matched}")
            print(f"Failed: {failed}")
            print(f"Success rate: {success_rate:.1f}%")
            
            action_type = {
                'playlist': 'added to playlist',
                'like': 'liked',
                'library': 'added to library'
            }[mode]
            print(f"Tracks were {action_type}")
            
            if failed_tracks:
                report_filename = f"{os.path.splitext(file)[0]}_failed_tracks.html"
                write_error_report(report_filename, failed_tracks)
                print(f"\nGenerated error report: {report_filename}")
    
    finally:
        # Re-enable sleep if we disabled it
        if caffeine_enabled:
            caffeine.off()

def add_song_to_playlist(session, song_id, playlist_id, playlist_track_ids=None, playlist_name=None):
    """Add a song to an Apple Music playlist"""
    song_id = str(song_id)
    equivalent_song_id = fetch_equivalent_song_id(session, song_id)
    
    if equivalent_song_id != song_id:
        if playlist_track_ids and equivalent_song_id in playlist_track_ids:
            return "DUPLICATE"
        song_id = equivalent_song_id
    
    try:
        request = session.post(
            f"https://amp-api.music.apple.com/v1/me/library/playlists/{playlist_id}/tracks",
            json={"data": [{"id": f"{song_id}", "type": "songs"}]}
        )
        
        if request.status_code in [200, 201, 204]:
            return "OK"
        else:
            return "ERROR"
    except Exception:
        return "ERROR"

def fetch_equivalent_song_id(session, song_id):
    """Fetch equivalent song ID if available"""
    try:
        request = session.get(f"https://amp-api.music.apple.com/v1/catalog/{country_code}/songs?filter[equivalents]={song_id}")
        if request.status_code == 200:
            data = json.loads(request.content.decode('utf-8'))
            return data['data'][0]['id']
        else:
            return song_id
    except:
        return song_id

def get_playlist_track_ids(session, playlist_id):
    """Get all track IDs from a playlist"""
    try:
        response = session.get(f"https://amp-api.music.apple.com/v1/me/library/playlists/{playlist_id}/tracks")
        if response.status_code == 200:
            return [track['attributes']['playParams']['catalogId'] for track in response.json()['data']]
        elif response.status_code == 404:
            return []
        else:
            raise Exception(f"Error {response.status_code} while getting playlist {playlist_id}!")
    except Exception as e:
        print(f"Error getting playlist tracks: {e}")
        return []

def enhance_itunes_match(search_results, title, artist, album, session):
    """Enhanced matching logic with confidence scoring and alternative matches"""
    matches = []
    
    normalized_search_title = clean_string(remove_features(title))
    normalized_search_artist = clean_string(artist)
    normalized_search_album = clean_string(album)
    
    for result in search_results:
        result_title = clean_string(remove_features(result['trackName']))
        result_artist = clean_string(result['artistName'])
        result_album = clean_string(result['collectionName'])
        
        # Calculate individual similarity scores
        title_score = get_string_similarity(normalized_search_title, result_title)
        artist_score = get_string_similarity(normalized_search_artist, result_artist)
        album_score = get_string_similarity(normalized_search_album, result_album)
        
        # Weighted scoring
        total_score = (title_score * 0.5) + (artist_score * 0.3) + (album_score * 0.2)
        
        # Get detailed track info for potential matches
        track_details = get_track_details(result['trackId'], session)
        if track_details:
            matches.append({
                'id': result['trackId'],
                'confidence': total_score,
                'details': track_details
            })
    
    # Sort matches by confidence
    matches.sort(key=lambda x: x['confidence'], reverse=True)
    
    if matches:
        best_match = matches[0]
        alternative_matches = matches[1:4]  # Keep top 3 alternatives
        
        if best_match['confidence'] >= 0.8:
            return MatchResult(
                track_id=best_match['id'],
                confidence=best_match['confidence'],
                match_method='high_confidence',
                alternative_matches=alternative_matches
            )
        else:
            return MatchResult(
                confidence=best_match['confidence'],
                alternative_matches=matches[:4]  # Include best match in alternatives
            )
    
    return MatchResult()

def get_itunes_id(title, artist, album, s):
    """Enhanced version of get_itunes_id with improved matching"""
    BASE_URL = f"https://itunes.apple.com/search?country={country_code}&media=music&entity=song&limit=10&term="
    
    try:
        # Different search strategies
        search_strategies = [
            (title, artist, album),  # Full search
            (remove_features(title), artist, album),  # Without features
            (title, artist, ""),  # Without album
            (remove_features(title), artist, ""),  # Without features and album
            (title, "", album),  # Without artist
            (remove_features(title), "", "")  # Title only, without features
        ]
        
        best_match = None
        highest_confidence = 0
        all_alternatives = []
        
        for search_title, search_artist, search_album in search_strategies:
            if not search_album and not search_artist:
                url = BASE_URL + urllib.parse.quote(search_title)
            elif not search_album:
                url = BASE_URL + urllib.parse.quote(f"{search_title} {search_artist}")
            else:
                url = BASE_URL + urllib.parse.quote(f"{search_title} {search_artist} {search_album}")
            
            try:
                request = urllib.request.Request(url)
                response = urllib.request.urlopen(request)
                data = json.loads(response.read().decode('utf-8'))
                
                if data['resultCount'] > 0:
                    match_result = enhance_itunes_match(data['results'], search_title, search_artist, search_album, s)
                    
                    if match_result.confidence > highest_confidence:
                        best_match = match_result
                        highest_confidence = match_result.confidence
                    
                    # Collect unique alternatives
                    for alt in match_result.alternative_matches:
                        if alt not in all_alternatives:
                            all_alternatives.append(alt)
            except:
                continue
        
        if best_match and best_match.track_id:
            best_match.alternative_matches = all_alternatives
            return best_match
        
        return MatchResult(alternative_matches=all_alternatives)
        
    except Exception:
        return MatchResult()

def match_isrc_to_itunes_id(session, album, album_artist, isrc):
    """Match track using ISRC code"""
    BASE_URL = f"https://amp-api.music.apple.com/v1/catalog/{country_code}/songs?filter[isrc]={isrc}"
    try:
        request = session.get(BASE_URL)
        if request.status_code == 200:
            data = json.loads(request.content.decode('utf-8'))
        else:
            raise Exception(f"Error {request.status_code}: {request.reason}")
            
        if not data.get("data"):
            return None
            
        # Try to match the song with the results
        for each in data['data']:
            isrc_album_name = clean_string(each['attributes']['albumName'])
            isrc_artist_name = clean_string(each['attributes']['artistName'])
            
            # Calculate similarity scores
            album_score = get_string_similarity(isrc_album_name, clean_string(album))
            artist_score = get_string_similarity(isrc_artist_name, clean_string(album_artist))
            
            # If both scores are high enough, consider it a match
            if album_score > 0.8 and artist_score > 0.8:
                return each['id']
            # If one score is very high and the other is reasonable
            elif (album_score > 0.9 and artist_score > 0.6) or (artist_score > 0.9 and album_score > 0.6):
                return each['id']
            # If album matches exactly
            elif isrc_album_name == clean_string(album):
                return each['id']
                
        return None
    except Exception as e:
        print(f"ISRC search failed: {e}")
        return None

def process_songs(file, mode='playlist'):
    """Process songs with progress bar showing track and artist"""
    failed_tracks = []
    
    # Prevent sleep on macOS if possible
    if caffeine_enabled:
        caffeine.on(display=True)
    
    try:
        with requests.Session() as s:
            s.headers.update({
                "Authorization": f"{token}",
                "media-user-token": f"{media_user_token}",
                "Cookie": f"{cookies}".encode('utf-8'),
                "Host": "amp-api.music.apple.com",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://music.apple.com/",
                "Origin": "https://music.apple.com",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
            })
            
            playlist_identifier = None
            playlist_track_ids = []
            playlist_name = None
            
            if mode == 'playlist':
                playlist_name = os.path.basename(file).split('.')[0].replace('_', ' ').capitalize()
                print(f"\nCreating playlist: {playlist_name}")
                playlist_identifier = create_apple_music_playlist(s, playlist_name)
                playlist_track_ids = get_playlist_track_ids(s, playlist_identifier)
                print()  # Add a blank line before progress bar
            
            # Count total tracks first
            with open(str(file), encoding='utf-8') as csvfile:
                total_tracks = sum(1 for row in csv.reader(csvfile)) - 1  # Subtract header row
            
            # Initialize progress bar
            progress = tqdm(
                total=total_tracks,
                desc="Starting...",
                unit="track",
                bar_format='{desc}: {percentage:3.0f}% |{bar}| {n_fmt}/{total_fmt} (Time remaining: {remaining})'
            )
            
            matched = 0
            failed = 0
            
            with open(str(file), encoding='utf-8') as csvfile:
                file_reader = csv.reader(csvfile)
                header_row = next(file_reader)
                
                if header_row[1] != 'Track Name' or header_row[3] != 'Artist Name(s)' or header_row[5] != 'Album Name' or header_row[16] != 'ISRC':
                    print('\nThe CSV file is not in the correct format!\nPlease be sure to download the CSV file(s) only from https://watsonbox.github.io/exportify/.\n\n')
                    return
                
                for row in file_reader:
                    title, artist, album, album_artist, isrc = [clean_string(x) for x in [row[1], row[3], row[5], row[7], row[16]]]
                    
                    # Update progress description with track and artist
                    track_info = f"{title} by {artist}"
                    if len(track_info) > 60:  # Truncate if too long
                        track_info = track_info[:57] + "..."
                    progress.set_description(track_info)
                    
                    # Try ISRC first
                    track_id = None
                    if isrc:
                        track_id = match_isrc_to_itunes_id(s, album, album_artist, isrc)
                    
                    # If ISRC fails, try text search
                    if not track_id:
                        match_result = get_itunes_id(title, artist, album, s)
                        if match_result.track_id:
                            track_id = match_result.track_id
                    
                    if track_id:
                        if mode == 'playlist':
                            result = add_song_to_playlist(s, track_id, playlist_identifier, playlist_track_ids, playlist_name)
                        elif mode == 'like':
                            result = like_track(s, track_id)
                        else:  # library mode
                            result = add_to_library(s, track_id)
                            
                        if result == "OK":
                            matched += 1
                        else:
                            failed += 1
                            failed_tracks.append({
                                'title': title,
                                'artist': artist,
                                'album': album,
                                'isrc': isrc,
                                'error': 'Failed to process'
                            })
                    else:
                        failed += 1
                        failed_tracks.append({
                            'title': title,
                            'artist': artist,
                            'album': album,
                            'isrc': isrc,
                            'alternatives': match_result.alternative_matches if 'match_result' in locals() else []
                        })
                    
                    progress.update(1)
                    sleep(delay)
            
            progress.close()
            
            # Generate report
            success_rate = (matched / total_tracks) * 100 if total_tracks > 0 else 0
            print(f"\n=== Processing Complete ===")
            print(f"Total tracks: {total_tracks}")
            print(f"Successfully processed: {matched}")
            print(f"Failed: {failed}")
            print(f"Success rate: {success_rate:.1f}%")
            
            action_type = {
                'playlist': 'added to playlist',
                'like': 'liked',
                'library': 'added to library'
            }[mode]
            print(f"Tracks were {action_type}")
            
            if failed_tracks:
                report_filename = f"{os.path.splitext(file)[0]}_failed_tracks.html"
                write_error_report(report_filename, failed_tracks)
                print(f"\nGenerated error report: {report_filename}")
    
    finally:
        # Re-enable sleep if we disabled it
        if caffeine_enabled:
            caffeine.off()

if __name__ == "__main__":
    # Get user tokens and connection data
    token = get_connection_data("token.dat", "\nPlease enter your Apple Music Authorization (Bearer token):\n")
    media_user_token = get_connection_data("media_user_token.dat", "\nPlease enter your media user token:\n")
    cookies = get_connection_data("cookies.dat", "\nPlease enter your cookies:\n")
    country_code = get_connection_data("country_code.dat", "\nPlease enter the country code (e.g., DE, UK, US etc.): ")
    
    # Show initial message about sleep prevention
    if platform.system() == 'Darwin' and not caffeine_enabled:
        print("\nNote: To prevent your Mac from sleeping during processing, install the caffeine package:")
        print("pip install caffeine\n")

    # Ask user for mode
    while True:
        print("\nChoose operation mode:")
        print("1) Create a playlist")
        print("2) Like all tracks")
        print("3) Add tracks to library")
        mode = input("Enter 1, 2, or 3: ").strip()
        if mode in ['1', '2', '3']:
            break
        print("Invalid input. Please enter 1, 2, or 3.")
    
    mode_map = {'1': 'playlist', '2': 'like', '3': 'library'}
    mode = mode_map[mode]

    if len(argv) > 1 and argv[1]:
        if ".csv" in argv[1]:
            process_songs(argv[1], mode)
        else:
            # Process all CSV files in directory
            files = [f for f in os.listdir(argv[1]) if os.path.isfile(os.path.join(argv[1], f)) and f.endswith('.csv')]
            for file in files:
                process_songs(os.path.join(argv[1], file), mode)