"use client";

import { useTiptap, useTiptapState } from "@tiptap/react";
import {
  Bold,
  Code,
  Italic,
  List,
  ListOrdered,
  Redo2,
  Strikethrough,
  TextQuote,
  Underline,
  Undo2,
} from "lucide-react";

import { ToolbarButton } from "@/components/editor/toolbar-button";

export function EditorToolbar() {
  const { editor } = useTiptap();
  const marks = useTiptapState((snapshot) => ({
    bold: snapshot.editor.isActive("bold"),
    italic: snapshot.editor.isActive("italic"),
    underline: snapshot.editor.isActive("underline"),
    strike: snapshot.editor.isActive("strike"),
    code: snapshot.editor.isActive("code"),
    bulletList: snapshot.editor.isActive("bulletList"),
    orderedList: snapshot.editor.isActive("orderedList"),
    blockquote: snapshot.editor.isActive("blockquote"),
    canUndo: snapshot.editor.can().undo(),
    canRedo: snapshot.editor.can().redo(),
  }));

  if (!editor) {
    return null;
  }

  return (
    <div
      role="toolbar"
      aria-label="Formatting toolbar"
      className="flex items-center gap-1 border-b border-border bg-surface px-4 py-1.5"
    >
      <ToolbarButton
        icon={Undo2}
        label="Undo"
        isDisabled={!marks.canUndo}
        onClick={() => editor.chain().focus().undo().run()}
      />
      <ToolbarButton
        icon={Redo2}
        label="Redo"
        isDisabled={!marks.canRedo}
        onClick={() => editor.chain().focus().redo().run()}
      />
      <div className="mx-1 h-5 w-px bg-border" aria-hidden />
      <ToolbarButton
        icon={Bold}
        label="Bold"
        isActive={marks.bold}
        onClick={() => editor.chain().focus().toggleBold().run()}
      />
      <ToolbarButton
        icon={Italic}
        label="Italic"
        isActive={marks.italic}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      />
      <ToolbarButton
        icon={Underline}
        label="Underline"
        isActive={marks.underline}
        onClick={() => editor.chain().focus().toggleUnderline().run()}
      />
      <ToolbarButton
        icon={Strikethrough}
        label="Strikethrough"
        isActive={marks.strike}
        onClick={() => editor.chain().focus().toggleStrike().run()}
      />
      <ToolbarButton
        icon={Code}
        label="Inline code"
        isActive={marks.code}
        onClick={() => editor.chain().focus().toggleCode().run()}
      />
      <div className="mx-1 h-5 w-px bg-border" aria-hidden />
      <ToolbarButton
        icon={List}
        label="Bullet list"
        isActive={marks.bulletList}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      />
      <ToolbarButton
        icon={ListOrdered}
        label="Ordered list"
        isActive={marks.orderedList}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      />
      <ToolbarButton
        icon={TextQuote}
        label="Blockquote"
        isActive={marks.blockquote}
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
      />
    </div>
  );
}
