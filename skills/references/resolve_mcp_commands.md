# DaVinci Resolve MCP コマンドクイックリファレンス

## プロジェクト管理

```
"新しいプロジェクト 'ProjectName' を作成して"
→ create_project("ProjectName")

"プロジェクト 'MyFilm' を開いて"
→ load_project("MyFilm")

"プロジェクトを保存して"
→ save_project()
```

## メディア管理

```
"/path/to/folder の動画を全部インポートして"
→ add_items_to_media_pool("/path/to/folder")

"メディアプールのクリップ一覧を見せて"
→ get_clip_metadata()

"メディアプールに 'Footage' フォルダを作って"
→ add_sub_folder("Footage")
```

## タイムライン操作

```
"'Assembly' というタイムラインを作って"
→ create_timeline("Assembly")

"メディアプールのクリップからタイムラインを作って"
→ create_timeline_from_clips("RoughCut")

"タイムラインのアイテム一覧を取得して"
→ get_timeline_items()

"現在のタイムコードを教えて"
→ get_current_timecode()
```

## マーカー

```
"現在位置に赤マーカーを追加して、メモは 'Check audio'"
→ add_timeline_marker(color="Red", note="Check audio")
```

## ページ切り替え

```
"カラーページに切り替えて"
→ open_page("color")

# 使用可能: media, cut, edit, fusion, color, fairlight, deliver
```

## カラーグレーディング

```
"カラーノードを追加して"
→ add_color_node()

"スティルを保存して"
→ save_still()

"ギャラリースティルを適用して"
→ apply_still()
```

## Fusion

```
"選択クリップにFusionコンポジションを作成して"
→ fusion_comp (add_tool action)

# 一般的なFusionノード:
# TextPlus, Background, Transform, Merge,
# ColorCorrector, DeltaKeyer, FastNoise
```

## レンダリング

```
"デリバーページでProRes 422 HQプリセットでレンダリング設定して"
→ open_page("deliver") + set_project_setting(render preset)

"レンダリングを開始して"
→ render_project()
```

## EDLインポート時の注意

Resolve へのEDLインポート:
1. File → Import → Timeline (EDL)
2. Project Settings → General Options → Conform Options
   → "Assist using reel names from: **Source clip filename**" を選択
3. リンク対象のビンを指定

MCP経由でのEDLインポートは直接的なAPIがないため、
ファイルシステム経由でResolveのメディアプールにEDLを追加する形になる。
