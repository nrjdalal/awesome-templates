bunx create-next-app@latest "$TEMP_DIR" --ts --eslint --tailwind --src-dir --app --turbopack --import-alias "@/*"
cd "$TEMP_DIR"
bunx shadcn@latest init -d
bunx shadcn@latest add -a
