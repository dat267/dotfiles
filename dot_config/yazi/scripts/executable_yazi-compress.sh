#!/bin/sh
printf "Format: (z)ip or (7)z? "
read -r fmt
case "$fmt" in
	z|zip) ext="zip"; flag="-tzip" ;;
	7|7z)  ext="7z";  flag="" ;;
	*) echo "Invalid"; read -p "Press Enter..."; exit 1 ;;
esac
printf "Output name: "
read -r name
[ -z "$name" ] && name="archive"
out="$name.$ext"
7z a -mmt=on -mx=5 $flag "$out" "$@"
echo
read -p "Press Enter to return to Yazi."
