import yt_dlp

def download_youtube_video(url, output_path="videos"):
    ydl_opts = {
    "format": "best[height<=1080]",  # 👈 instead of video+audio
    "outtmpl": f"{output_path}/%(title)s.%(ext)s",
    "noplaylist": True,
    }

    def duration_filter(info):
        # Skip videos longer than 2 minutes (120 sec)
        duration = info.get("duration", 0)
        return duration and duration <= 120

    ydl_opts["match_filter"] = lambda info: None if duration_filter(info) else "Video too long"

    import os
    os.makedirs(output_path, exist_ok=True)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


# Example usage
download_youtube_video("https://www.youtube.com/watch?v=Q9xp5WMQk2U")