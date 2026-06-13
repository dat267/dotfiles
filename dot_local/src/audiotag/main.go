package main

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"

	"github.com/bogem/id3v2/v2"
	"github.com/go-flac/flacvorbis/v2"
	"github.com/go-flac/go-flac/v2"
	"github.com/spf13/cobra"
)

var version = "dev"
var moveFlag bool
var concurrency int

func main() {
	var rootCmd = &cobra.Command{
		Use:   "audiotag",
		Short: "audiotag is a CLI tool to tag and organize music files",
		Long:  `audiotag can tag MP3/FLAC files based on their directory structure, or organize music files into a clean directory structure based on their tags.`,
	}

	var tagCmd = &cobra.Command{
		Use:   "tag <directory>",
		Short: "Tag music files based on their directory path and filename",
		Long: `Walks a directory and tags MP3 and FLAC files based on their parent directory names and filenames.
Expected directory structure: .../Artist/Album/Track - Title.ext`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			root := args[0]
			info, err := os.Stat(root)
			if err != nil {
				return err
			}
			if !info.IsDir() {
				return fmt.Errorf("%s is not a directory", root)
			}

			// Collect files to process
			var files []string
			err = filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
				if err != nil {
					return nil
				}
				if info.IsDir() {
					return nil
				}
				ext := strings.ToLower(filepath.Ext(path))
				if ext == ".mp3" || ext == ".flac" {
					files = append(files, path)
				}
				return nil
			})
			if err != nil {
				return err
			}

			// Process concurrently using a semaphore
			if concurrency <= 0 {
				concurrency = 1
			}
			sem := make(chan struct{}, concurrency)
			var wg sync.WaitGroup

			for _, path := range files {
				wg.Add(1)
				go func(p string) {
					defer wg.Done()
					sem <- struct{}{}
					defer func() { <-sem }()

					ext := strings.ToLower(filepath.Ext(p))
					tagFile(p, ext)
				}(path)
			}
			wg.Wait()
			return nil
		},
	}

	var organizeCmd = &cobra.Command{
		Use:   "organize <source_dir> <dest_dir>",
		Short: "Organize music files into a clean structure based on their tags",
		Long: `Reads the tags of MP3 and FLAC files in <source_dir> and copies (or moves) them into <dest_dir>
under the structure: <dest_dir>/<Artist>/<Album>/<Track> - <Title>.<ext>`,
		Args: cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			srcDir := args[0]
			destDir := args[1]

			srcInfo, err := os.Stat(srcDir)
			if err != nil {
				return err
			}
			if !srcInfo.IsDir() {
				return fmt.Errorf("%s is not a directory", srcDir)
			}

			absSrcDir, err := filepath.Abs(srcDir)
			if err != nil {
				return err
			}
			absDestDir, err := filepath.Abs(destDir)
			if err != nil {
				return err
			}

			// Ensure destDir exists (or create it)
			if err := os.MkdirAll(destDir, 0755); err != nil {
				return fmt.Errorf("failed to create destination directory: %w", err)
			}

			// Collect files to process
			var files []string
			err = filepath.Walk(srcDir, func(path string, info os.FileInfo, err error) error {
				if err != nil {
					return nil
				}

				absPath, err := filepath.Abs(path)
				if err != nil {
					return nil
				}

				// Skip walking the destination directory to avoid infinite loops / reprocessing
				if strings.HasPrefix(absPath, absDestDir) {
					if info.IsDir() {
						return filepath.SkipDir
					}
					return nil
				}

				// Skip the source root directory directory node itself
				if absPath == absSrcDir && info.IsDir() {
					return nil
				}

				if info.IsDir() {
					return nil
				}
				ext := strings.ToLower(filepath.Ext(path))
				if ext == ".mp3" || ext == ".flac" {
					files = append(files, path)
				}
				return nil
			})
			if err != nil {
				return err
			}

			// Process concurrently using a semaphore
			if concurrency <= 0 {
				concurrency = 1
			}
			sem := make(chan struct{}, concurrency)
			var wg sync.WaitGroup
			var mu sync.Mutex

			for _, path := range files {
				wg.Add(1)
				go func(p string) {
					defer wg.Done()
					sem <- struct{}{}
					defer func() { <-sem }()

					ext := strings.ToLower(filepath.Ext(p))
					if err := organizeFile(p, ext, destDir, moveFlag); err != nil {
						mu.Lock()
						fmt.Fprintf(os.Stderr, "Error organizing %s: %v\n", p, err)
						mu.Unlock()
					}
				}(path)
			}
			wg.Wait()
			return nil
		},
	}

	organizeCmd.Flags().BoolVarP(&moveFlag, "move", "m", false, "Move files instead of copying them")

	rootCmd.PersistentFlags().IntVarP(&concurrency, "concurrency", "c", runtime.NumCPU(), "number of concurrent workers")

	rootCmd.AddCommand(tagCmd)
	rootCmd.AddCommand(organizeCmd)

	rootCmd.Version = version
	rootCmd.SetVersionTemplate("audiotag version {{.Version}}\n")

	if err := rootCmd.Execute(); err != nil {
		os.Exit(1)
	}
}

func tagFile(path string, ext string) {
	abs, err := filepath.Abs(path)
	if err != nil {
		return
	}
	parts := strings.Split(abs, string(filepath.Separator))
	if len(parts) < 3 {
		return
	}
	album := parts[len(parts)-2]
	artist := parts[len(parts)-3]
	filename := strings.TrimSuffix(parts[len(parts)-1], filepath.Ext(path))
	track := ""
	title := filename
	if idx := strings.Index(filename, "__"); idx != -1 {
		artist = strings.TrimSpace(filename[idx+2:])
		filename = strings.TrimSpace(filename[:idx])
	}
	if idx := strings.Index(filename, "-"); idx != -1 {
		track = strings.TrimSpace(filename[:idx])
		title = strings.TrimSpace(filename[idx+1:])
	}
	if ext == ".mp3" {
		tagMP3(path, artist, album, title, track)
		return
	}
	if ext == ".flac" {
		tagFLAC(path, artist, album, title, track)
	}
}

func tagMP3(path, artist, album, title, track string) {
	tag, err := id3v2.Open(path, id3v2.Options{Parse: true})
	if err != nil {
		return
	}
	defer tag.Close()
	compatibleArtist := strings.ReplaceAll(artist, ";", " / ")

	// Optimization: Skip saving if tags are already correct
	if tag.Artist() == compatibleArtist &&
		tag.Album() == album &&
		tag.Title() == title &&
		trackNumMatches(tag.GetTextFrame("TRCK").Text, track) {
		return
	}

	tag.SetArtist(compatibleArtist)
	tag.SetAlbum(album)
	tag.SetTitle(title)
	if track != "" {
		tag.DeleteFrames("TRCK")
		tag.AddTextFrame("TRCK", id3v2.EncodingUTF8, track)
	}
	tag.Save()
	fmt.Printf("Tagged: %s\n", path)
}

func findVorbisComment(meta []*flac.MetaDataBlock) (*flacvorbis.MetaDataBlockVorbisComment, int) {
	for idx, block := range meta {
		if block.Type != flac.VorbisComment {
			continue
		}
		cmt, err := flacvorbis.ParseFromMetaDataBlock(*block)
		if err == nil {
			return cmt, idx
		}
	}
	return flacvorbis.New(), -1
}

func tagFLAC(path, artist, album, title, track string) {
	f, err := flac.ParseFile(path)
	if err != nil {
		return
	}
	cmt, cmtIdx := findVorbisComment(f.Meta)

	// Clean target values
	artists := strings.Split(artist, ";")
	var targetArtists []string
	for _, a := range artists {
		targetArtists = append(targetArtists, strings.TrimSpace(a))
	}
	targetArtistJoined := strings.Join(targetArtists, "; ")

	// Helper to check if a specific key has the correct value
	hasCorrectValue := func(key, val string) bool {
		vals, err := cmt.Get(key)
		if err != nil || len(vals) == 0 {
			return val == ""
		}
		return strings.Join(vals, "; ") == val
	}

	// Helper to check if the track comment matches
	hasCorrectTrack := func() bool {
		vals, err := cmt.Get(flacvorbis.FIELD_TRACKNUMBER)
		if err != nil || len(vals) == 0 {
			return track == ""
		}
		return trackNumMatches(strings.Join(vals, "; "), track)
	}

	// Optimization: Skip saving if tags are already correct
	if cmtIdx >= 0 &&
		hasCorrectValue(flacvorbis.FIELD_ARTIST, targetArtistJoined) &&
		hasCorrectValue(flacvorbis.FIELD_ALBUM, album) &&
		hasCorrectValue(flacvorbis.FIELD_TITLE, title) &&
		hasCorrectTrack() {
		return
	}

	// Clear existing keys to prevent duplication before writing new values
	deleteVorbisKey(cmt, flacvorbis.FIELD_ARTIST)
	deleteVorbisKey(cmt, flacvorbis.FIELD_ALBUM)
	deleteVorbisKey(cmt, flacvorbis.FIELD_TITLE)
	deleteVorbisKey(cmt, flacvorbis.FIELD_TRACKNUMBER)

	for _, a := range targetArtists {
		cmt.Add(flacvorbis.FIELD_ARTIST, a)
	}
	cmt.Add(flacvorbis.FIELD_ALBUM, album)
	cmt.Add(flacvorbis.FIELD_TITLE, title)
	if track != "" {
		cmt.Add(flacvorbis.FIELD_TRACKNUMBER, track)
	}
	cmtsmeta := cmt.Marshal()
	if cmtIdx >= 0 {
		f.Meta[cmtIdx] = &cmtsmeta
	} else {
		f.Meta = append(f.Meta, &cmtsmeta)
	}
	f.Save(path)
	fmt.Printf("Tagged: %s\n", path)
}

func deleteVorbisKey(cmt *flacvorbis.MetaDataBlockVorbisComment, key string) {
	keyPrefix := strings.ToUpper(key) + "="
	var newComments []string
	for _, comment := range cmt.Comments {
		if !strings.HasPrefix(strings.ToUpper(comment), keyPrefix) {
			newComments = append(newComments, comment)
		}
	}
	cmt.Comments = newComments
}

func trackNumMatches(tagTrack, fileTrack string) bool {
	// If the parsed file track is empty, we don't want to set/write it anyway, so it matches.
	if fileTrack == "" {
		return true
	}
	tagTrack = strings.TrimSpace(tagTrack)
	if idx := strings.Index(tagTrack, "/"); idx != -1 {
		tagTrack = strings.TrimSpace(tagTrack[:idx])
	}
	t1 := strings.TrimLeft(tagTrack, "0")
	t2 := strings.TrimLeft(fileTrack, "0")
	if t1 == "" { t1 = "0" }
	if t2 == "" { t2 = "0" }
	return t1 == t2
}

func organizeFile(srcPath, ext, destDir string, move bool) error {
	var artist, album, title, track string
	var err error

	switch ext {
	case ".mp3":
		artist, album, title, track, err = readMP3Tags(srcPath)
	case ".flac":
		artist, album, title, track, err = readFLACTags(srcPath)
	}

	if err != nil {
		return fmt.Errorf("failed to read tags: %w", err)
	}

	// Fallbacks
	baseName := strings.TrimSuffix(filepath.Base(srcPath), filepath.Ext(srcPath))
	if artist == "" {
		artist = "Unknown Artist"
	}
	if album == "" {
		album = "Unknown Album"
	}
	if title == "" {
		title = baseName
	}

	// Sanitize parts for directory and file names
	artist = sanitizeName(artist)
	album = sanitizeName(album)
	title = sanitizeName(title)

	// Format track number (e.g. pad single digits)
	trackStr := strings.TrimSpace(track)
	if idx := strings.Index(trackStr, "/"); idx != -1 {
		trackStr = trackStr[:idx]
	}
	trackStr = strings.TrimSpace(trackStr)
	if len(trackStr) == 1 && trackStr[0] >= '0' && trackStr[0] <= '9' {
		trackStr = "0" + trackStr
	}

	// Construct target path
	targetDir := filepath.Join(destDir, artist, album)
	var targetFilename string
	if trackStr != "" {
		targetFilename = fmt.Sprintf("%s - %s%s", trackStr, title, ext)
	} else {
		targetFilename = fmt.Sprintf("%s%s", title, ext)
	}
	targetPath := filepath.Join(targetDir, targetFilename)

	// Clean/absolute paths to verify if we are copying to the same file
	absSrc, err := filepath.Abs(srcPath)
	if err != nil {
		return err
	}
	absDst, err := filepath.Abs(targetPath)
	if err != nil {
		return err
	}
	if absSrc == absDst {
		// Already at target path, do nothing
		return nil
	}

	// Create directories if they do not exist
	if err := os.MkdirAll(targetDir, 0755); err != nil {
		return fmt.Errorf("failed to create directory %s: %w", targetDir, err)
	}

	if move {
		if err := moveFile(srcPath, targetPath); err != nil {
			return fmt.Errorf("failed to move file to %s: %w", targetPath, err)
		}
		fmt.Printf("Moved: %s -> %s\n", srcPath, targetPath)
	} else {
		if err := copyFile(srcPath, targetPath); err != nil {
			return fmt.Errorf("failed to copy file to %s: %w", targetPath, err)
		}
		fmt.Printf("Copied: %s -> %s\n", srcPath, targetPath)
	}

	return nil
}

func sanitizeName(name string) string {
	invalidChars := []string{"/", "\\", "?", "%", "*", ":", "|", "\"", "<", ">"}
	res := name
	for _, c := range invalidChars {
		res = strings.ReplaceAll(res, c, "-")
	}
	res = strings.TrimSpace(res)
	if res == "" {
		res = "Unknown"
	}
	return res
}

func readMP3Tags(path string) (artist, album, title, track string, err error) {
	tag, err := id3v2.Open(path, id3v2.Options{Parse: true})
	if err != nil {
		return "", "", "", "", err
	}
	defer tag.Close()
	return tag.Artist(), tag.Album(), tag.Title(), tag.GetTextFrame("TRCK").Text, nil
}

func readFLACTags(path string) (artist, album, title, track string, err error) {
	f, err := flac.ParseFile(path)
	if err != nil {
		return "", "", "", "", err
	}
	cmt, _ := findVorbisComment(f.Meta)
	if cmt == nil {
		return "", "", "", "", nil
	}

	getVal := func(key string) string {
		vals, err := cmt.Get(key)
		if err == nil && len(vals) > 0 {
			return strings.Join(vals, "; ")
		}
		return ""
	}

	artist = getVal(flacvorbis.FIELD_ARTIST)
	album = getVal(flacvorbis.FIELD_ALBUM)
	title = getVal(flacvorbis.FIELD_TITLE)
	track = getVal(flacvorbis.FIELD_TRACKNUMBER)

	return artist, album, title, track, nil
}

func moveFile(src, dst string) error {
	err := os.Rename(src, dst)
	if err == nil {
		return nil
	}
	// Fallback to copy and delete
	if err := copyFile(src, dst); err != nil {
		return err
	}
	return os.Remove(src)
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.Copy(out, in)
	if err != nil {
		return err
	}
	return out.Sync()
}
