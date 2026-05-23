import { useState } from 'react'
import Editor from '@monaco-editor/react'
import jsyaml from 'js-yaml'

interface YAMLEditorProps {
  value: string
  onChange: (value: string) => void
  onSave: () => void
  validationError?: string | null
}

export default function YAMLEditor({ value, onChange, onSave, validationError }: YAMLEditorProps) {
  const [error, setError] = useState<string | null>(null)

  function handleEditorChange(val: string | undefined) {
    const newValue = val || ''
    onChange(newValue)
    // Live YAML validation
    try {
      jsyaml.load(newValue)
      setError(null)
    } catch (e: any) {
      setError(e.message)
    }
  }

  const displayError = validationError || error

  return (
    <div>
      <div className="border border-border rounded-lg overflow-hidden h-[500px]">
        <Editor
          height="100%"
          defaultLanguage="yaml"
          value={value}
          onChange={handleEditorChange}
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            tabSize: 2,
            scrollBeyondLastLine: true,
            wordWrap: 'on',
          }}
        />
      </div>
      {displayError && (
        <div className="text-error text-xs mt-2 font-mono">{displayError}</div>
      )}
      <div className="flex gap-2 mt-3">
        <button
          onClick={onSave}
          disabled={!!displayError}
          className="px-4 py-1.5 text-sm bg-accent text-bg rounded-md hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Save
        </button>
      </div>
    </div>
  )
}
