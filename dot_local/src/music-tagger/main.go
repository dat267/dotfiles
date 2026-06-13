package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/bogem/id3v2/v2"
	"github.com/go-flac/flacvorbis/v2"
	"github.com/go-flac/go-flac/v2"
	"github.com/spf13/cobra"
)

var version = "dev"

func main() {
	var rootCmd = &cobra.Command{
		Use:   "music-tagger <directory>",
		Short: "music-tagger is a directory-based music tagger for MP3 and FLAC files",
		Long: `A CLI tool that walks a directory tree and tags MP3 and FLAC files
based on their parent directory names and filenames.
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
			return filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
				if err != nil {
					return nil
				}
				if info.IsDir() {
					return nil
				}
				ext := strings.ToLower(filepath.Ext(path))
				if ext == ".mp3" || ext == ".flac" {
					tagFile(path, ext)
				}
				return nil
			})
		},
	}

	rootCmd.Version = version
	rootCmd.SetVersionTemplate("music-tagger version {{.Version}}\n")

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
	tag.SetArtist(compatibleArtist)
	tag.SetAlbum(album)
	tag.SetTitle(title)
	if track != "" {
		tag.AddTextFrame(tag.CommonID("Track number"), id3v2.EncodingUTF8, track)
	}
	tag.Save()
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
	artists := strings.Split(artist, ";")
	for _, a := range artists {
		cmt.Add(flacvorbis.FIELD_ARTIST, strings.TrimSpace(a))
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
}
