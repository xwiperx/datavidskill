#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  export_qualities.sh <master.mp4> <output-dir> <resolution...>

Resolutions: 144p 240p 360p 480p 720p 1080p
Example:
  export_qualities.sh render.mp4 output 144p 360p 720p 1080p

Creates <master-stem>_<resolution>.mp4 for each requested size. Existing files
are never overwritten. Aspect ratio is preserved with padding, not cropping.
EOF
}

if [[ $# -lt 3 ]]; then usage >&2; exit 2; fi
input=$1
outdir=$2
shift 2

if [[ ! -f "$input" ]]; then echo "Input file not found: $input" >&2; exit 1; fi
command -v ffmpeg >/dev/null || { echo 'ffmpeg is required' >&2; exit 1; }
command -v ffprobe >/dev/null || { echo 'ffprobe is required' >&2; exit 1; }

mkdir -p "$outdir"
base=$(basename -- "$input")
stem=${base%.*}

for quality in "$@"; do
  case "$quality" in
    144p) width=256; height=144 ;;
    240p) width=426; height=240 ;;
    360p) width=640; height=360 ;;
    480p) width=854; height=480 ;;
    720p) width=1280; height=720 ;;
    1080p) width=1920; height=1080 ;;
    *) echo "Unsupported resolution: $quality" >&2; usage >&2; exit 2 ;;
  esac

  output="$outdir/${stem}_${quality}.mp4"
  if [[ -e "$output" ]]; then
    echo "Refusing to overwrite existing file: $output" >&2
    exit 1
  fi

  source_width=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$input")
  source_height=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$input")
  if [[ "$quality" == 1080p && "$source_width" == 1920 && "$source_height" == 1080 ]]; then
    echo "Source is already 1080p; preserving the master bit-for-bit -> $output"
    cp --reflink=auto -- "$input" "$output"
    continue
  fi

  echo "Encoding $quality (${width}x${height}) -> $output"
  vf="scale=${width}:${height}:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos,pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
  ffmpeg -hide_banner -nostdin -loglevel error -i "$input" \
    -map 0:v:0 -map '0:a?' \
    -vf "$vf" \
    -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p \
    -c:a aac -b:a 128k -ar 44100 \
    -movflags +faststart "$output"

  ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,codec_name \
    -show_entries format=duration,size -of default=noprint_wrappers=1 "$output"
done
