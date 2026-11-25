#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  export_qualities.sh <master.mp4> <output-dir> <resolution...>

Resolutions: 144p 240p 360p 480p 720p 1080p
Existing deliverables are preserved; collisions receive _v2, _v3, ... suffixes.
Aspect ratio is preserved with padding, not cropping.
Optional: set DATAVID_AUDIO_SOURCE=/path/to/normalized.wav to encode audio
directly from PCM and avoid transcoding the master's AAC track.
EOF
}
[[ $# -ge 3 ]] || { usage >&2; exit 2; }
input=$1; outdir=$2; shift 2
[[ -f "$input" ]] || { echo "Input file not found: $input" >&2; exit 1; }
audio_source=${DATAVID_AUDIO_SOURCE:-$input}
[[ -f "$audio_source" ]] || { echo "Audio source file not found: $audio_source" >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo 'ffmpeg is required' >&2; exit 1; }
command -v ffprobe >/dev/null || { echo 'ffprobe is required' >&2; exit 1; }
mkdir -p "$outdir"
base=$(basename -- "$input"); stem=${base%.*}

unique_path() {
  local basepath=$1 candidate=$1 n=2 ext
  while [[ -e "$candidate" ]]; do
    ext=${basepath##*.}
    candidate="${basepath%.*}_v${n}.${ext}"
    ((n+=1))
  done
  printf '%s\n' "$candidate"
}

source_width=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$input")
source_height=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$input")
source_fps=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$input")
declare -A seen=()
for quality in "$@"; do
  [[ -z "${seen[$quality]+x}" ]] || continue
  seen[$quality]=1
  case "$quality" in
    144p) width=256; height=144 ;;
    240p) width=426; height=240 ;;
    360p) width=640; height=360 ;;
    480p) width=854; height=480 ;;
    720p) width=1280; height=720 ;;
    1080p) width=1920; height=1080 ;;
    *) echo "Unsupported resolution: $quality" >&2; usage >&2; exit 2 ;;
  esac
  output=$(unique_path "$outdir/${stem}_${quality}.mp4")
  temp="$outdir/.${stem}_${quality}.$$.tmp.mp4"
  [[ ! -e "$temp" ]] || { echo "Temporary file already exists: $temp" >&2; exit 1; }
  echo "Encoding $quality (${width}x${height}) -> $output"
  if [[ "$quality" == 1080p && "$source_width" == 1920 && "$source_height" == 1080 && "$audio_source" == "$input" ]]; then
    cp --reflink=auto -- "$input" "$temp"
  else
    vf="scale=${width}:${height}:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos,pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
    inputs=(-i "$input")
    if [[ "$audio_source" == "$input" ]]; then
      audio_map='0:a?'
    else
      inputs+=(-i "$audio_source")
      audio_map='1:a:0'
    fi
    ffmpeg -hide_banner -nostdin -loglevel error "${inputs[@]}" \
      -map 0:v:0 -map "$audio_map" -vf "$vf" \
      -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p \
      -c:a aac -b:a 128k -ar 44100 -shortest -movflags +faststart "$temp"
  fi
  mapfile -t metadata < <(ffprobe -v error -select_streams v:0 \
    -show_entries stream=width,height,r_frame_rate \
    -of default=noprint_wrappers=1:nokey=1 "$temp")
  actual_w=${metadata[0]:-}; actual_h=${metadata[1]:-}; actual_fps=${metadata[2]:-}
  if [[ "$actual_w" != "$width" || "$actual_h" != "$height" || "$actual_fps" != "$source_fps" ]]; then
    rm -f -- "$temp"
    echo "Output metadata mismatch for $quality: ${actual_w}x${actual_h} @ ${actual_fps}" >&2
    exit 1
  fi
  if ! ffmpeg -v error -i "$temp" -f null -; then
    rm -f -- "$temp"
    echo "Full decode failed for $quality" >&2
    exit 1
  fi
  # Hard-link publication is atomic and fails rather than overwriting a file.
  if ! ln -- "$temp" "$output"; then
    rm -f -- "$temp"
    echo "Could not publish without overwriting: $output" >&2
    exit 1
  fi
  rm -f -- "$temp"
  ffprobe -v error -show_entries stream=width,height,r_frame_rate,codec_name -show_entries format=duration,size \
    -of default=noprint_wrappers=1 "$output"
done
