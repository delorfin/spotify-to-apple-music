# Import Spotify playlists to Apple Music

Initially based on [https://github.com/nf1973/Spotify-2-AppleMusic](https://github.com/nf1973/Spotify-2-AppleMusic)

Allows you to:
- Add/update a playlist
- Add tracks to the library
- Favorite the tracks

## Usage

### 1. Export your Spotify Playlist to a CSV file

The first step is getting the tracks you want to import into Apple Music into a CSV file. The simplest way to do this is to use [**Exportify**](https://watsonbox.github.io/exportify/).

You just need to login using your Spotify account, and all the playlists that you have saved in your library should appear. Then export the CSV file of the playlist you want to convert and save it in the same directory as the directory where you cloned the repo.

### 2. Match the Spotify tracks with their Apple Music identifier and upload them to Apple Music

To upload your converted IDs to an Apple Music playlist, you'll need 5 things:
- The list of Apple Music identifiers (iTunes identifiers) for each track in your Spotify playlist
- Your Apple Music Authorization (Bearer Token)
- Your Apple Music Media-User-Token
- Your session cookies

Here's a step by step to get all of this data:
1. To get the list of Apple Music identifiers, all you got to do is get the file you downloaded from [**Exportify**](https://watsonbox.github.io/exportify/).
2. You can get all the other data using your favorite browser. Fire it up and open the [**Apple Music web player**](https://music.apple.com/).
3. Open DevTools (**Ctrl + Shift + I or Cmd + Opt + I**) and go to the Network tab.
4. Then you'll need to log in to your account. If you're already logged in, please log out and log in again.
5. Go back to the DevTools and look for a GET request to [***https://buy.music.apple.com/account/web/info***](https://buy.music.apple.com/account/web/info) (It seems like there are 2 requests to this URL; it should be the second one).
6. In the **Requests Headers**, copy the **Authorization** (Please make sure to copy the `Bearer` part), the **Media-User-Token** and the **Cookies**.

   **ALL THIS DATA IS CASE SENSITIVE**. PLEASE MAKE SURE TO COPY IT RIGHT.
7. Now you're finally ready to connvert your tracks and push them onto your Apple Music playlist. To do so, open a terminal and run the following:

```
python3 convert.py yourplaylist.csv
```

or

```
python3 convert.py playlistdir
```

(Replace *yourplaylist.csv* by your own filename, the one you got from [**Exportify**](https://watsonbox.github.io/exportify/), or *playlistdir* by your own playlist directory name with all the `.csv` files you want to convert.)

Follow the script prompt, and when asked, paste in each data. If your terminal have a paste character limit: please hardcode them OR put them into separate files named as following: `token.dat`, `media_user_token.dat` and `cookies.dat`.

Please note that **the best practice** is to put your connection data as it can be reuse in a near future. Keep in mind that, those connection data will expire and you might need to get them again.

## Limitations & Notes

### iTunes StoreFront Region

Please note that the current script needs to be configured with the iTunes StoreFront of **your Region**. Full list of ISO Code, provided by Wikipedia, [**here**](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2). You can put the code in the `country_code.dat` file.

### Missing tracks

After the script finishes, an HTML file with all the not-found tracks will be created, featuring links to help in manual searches.
