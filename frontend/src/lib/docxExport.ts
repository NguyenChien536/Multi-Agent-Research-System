import {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  Table,
  TableRow,
  TableCell,
  WidthType,
  BorderStyle,
  AlignmentType,
  ShadingType
} from 'docx';

export interface DocxExportOptions {
  title: string;
  markdownContent: string;
  completedAt?: string;
  researchType?: string;
  filename?: string;
}

function parseInlineRuns(text: string): TextRun[] {
  // Regex to split by bold, italic, code, citation [1], markdown link [text](url)
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|\[\d+\]|\[src_\d+\])/g;
  const parts = text.split(regex);
  const runs: TextRun[] = [];

  for (const part of parts) {
    if (!part) continue;

    if (part.startsWith('**') && part.endsWith('**')) {
      runs.push(new TextRun({
        text: part.slice(2, -2),
        bold: true,
        size: 23 // ~11.5pt
      }));
    } else if (part.startsWith('*') && part.endsWith('*')) {
      runs.push(new TextRun({
        text: part.slice(1, -1),
        italics: true,
        size: 23
      }));
    } else if (part.startsWith('`') && part.endsWith('`')) {
      runs.push(new TextRun({
        text: part.slice(1, -1),
        font: 'Consolas',
        size: 20, // 10pt
        shading: {
          fill: 'F3F4F6',
          type: ShadingType.CLEAR,
          color: 'auto'
        }
      }));
    } else if (/^\[(\d+|src_\d+)\]$/.test(part)) {
      runs.push(new TextRun({
        text: part,
        bold: true,
        color: '1D4ED8', // blue
        size: 21
      }));
    } else if (/^\[([^\]]+)\]\(([^)]+)\)$/.test(part)) {
      const match = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (match) {
        runs.push(new TextRun({
          text: match[1],
          color: '1D4ED8',
          underline: {},
          size: 23
        }));
      }
    } else {
      runs.push(new TextRun({
        text: part,
        size: 23 // ~11.5pt
      }));
    }
  }

  return runs.length > 0 ? runs : [new TextRun({ text, size: 23 })];
}

export async function createPaperDocx(options: DocxExportOptions): Promise<Blob> {
  const {
    title,
    markdownContent,
    completedAt,
    researchType,
  } = options;

  const docChildren: (Paragraph | Table)[] = [];

  // 1. Academic Journal Masthead Top Line
  docChildren.push(
    new Paragraph({
      spacing: { before: 0, after: 80 },
      alignment: AlignmentType.RIGHT,
      children: [
        new TextRun({
          text: 'SYNTHIA • RESEARCH DRAFT',
          bold: true,
          size: 18,
          color: '4B5563'
        }),
        new TextRun({
          text: completedAt ? `  •  ${completedAt}` : '',
          size: 18,
          color: '6B7280'
        })
      ]
    })
  );

  // Type tag
  if (researchType) {
    docChildren.push(
      new Paragraph({
        spacing: { before: 0, after: 120 },
        children: [
          new TextRun({
            text: researchType.toUpperCase(),
            bold: true,
            size: 18,
            color: '1E3A8A' // indigo
          })
        ]
      })
    );
  }

  // 2. Paper Title
  docChildren.push(
    new Paragraph({
      heading: HeadingLevel.TITLE,
      spacing: { before: 160, after: 200 },
      children: [
        new TextRun({
          text: title,
          bold: true,
          size: 38, // 19pt
          color: '111827'
        })
      ]
    })
  );

  docChildren.push(new Paragraph({
    children: [new TextRun({text: 'AI-assisted draft. Verify claims and references before use. Figure assets are available in the publication ZIP.', italics: true, size: 18})]
  }));

  // Divider line
  docChildren.push(
    new Paragraph({
      border: {
        bottom: {
          color: 'E5E7EB',
          space: 1,
          style: BorderStyle.SINGLE,
          size: 6
        }
      },
      spacing: { before: 120, after: 240 }
    })
  );

  // 5. Body Content Parsing
  const lines = markdownContent.replace(/^# [^\n]+\n?/, '').split('\n');
  let inTable = false;
  let tableRows: string[][] = [];

  const flushTable = () => {
    if (inTable && tableRows.length > 0) {
      const headerRow = tableRows[0];
      const bodyRows = tableRows.slice(1);

      const docxRows: TableRow[] = [];

      // Header row
      docxRows.push(
        new TableRow({
          tableHeader: true,
          children: headerRow.map(cell => new TableCell({
            children: [
              new Paragraph({
                children: parseInlineRuns(cell.trim()).map(r => {
                  return new TextRun({ ...r, bold: true, size: 20 });
                }),
                spacing: { before: 60, after: 60 }
              })
            ],
            shading: {
              fill: 'F3F4F6',
              type: ShadingType.CLEAR,
              color: 'auto'
            }
          }))
        })
      );

      // Body rows
      for (const row of bodyRows) {
        docxRows.push(
          new TableRow({
            children: row.map(cell => new TableCell({
              children: [
                new Paragraph({
                  children: parseInlineRuns(cell.trim()).map(r => new TextRun({ ...r, size: 20 })),
                  spacing: { before: 40, after: 40 }
                })
              ]
            }))
          })
        );
      }

      docChildren.push(
        new Table({
          width: { size: 100, type: WidthType.PERCENTAGE },
          rows: docxRows
        })
      );

      // Spacing after table
      docChildren.push(new Paragraph({ spacing: { before: 120, after: 120 } }));
      inTable = false;
      tableRows = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const line = rawLine.trim();

    // Table rows
    if (line.startsWith('|') && line.endsWith('|')) {
      if (/^\|[-|\s]+\|$/.test(line)) {
        continue; // skip separator row
      }
      const cells = line.slice(1, -1).split('|');
      inTable = true;
      tableRows.push(cells);
      continue;
    } else if (inTable) {
      flushTable();
    }

    // Skip empty lines
    if (!line) {
      continue;
    }

    // Headings
    if (line.startsWith('# ')) {
      docChildren.push(
        new Paragraph({
          heading: HeadingLevel.HEADING_1,
          spacing: { before: 320, after: 140 },
          children: [
            new TextRun({
              text: line.slice(2).trim(),
              bold: true,
              size: 30, // 15pt
              color: '111827'
            })
          ]
        })
      );
      continue;
    }
    if (line.startsWith('## ')) {
      docChildren.push(
        new Paragraph({
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 260, after: 100 },
          children: [
            new TextRun({
              text: line.slice(3).trim(),
              bold: true,
              size: 26, // 13pt
              color: '1F2937'
            })
          ]
        })
      );
      continue;
    }
    if (line.startsWith('### ')) {
      docChildren.push(
        new Paragraph({
          heading: HeadingLevel.HEADING_3,
          spacing: { before: 200, after: 80 },
          children: [
            new TextRun({
              text: line.slice(4).trim(),
              bold: true,
              size: 24, // 12pt
              color: '374151'
            })
          ]
        })
      );
      continue;
    }
    if (line.startsWith('#### ')) {
      docChildren.push(
        new Paragraph({
          heading: HeadingLevel.HEADING_4,
          spacing: { before: 160, after: 60 },
          children: [
            new TextRun({
              text: line.slice(5).trim(),
              bold: true,
              size: 22,
              color: '4B5563'
            })
          ]
        })
      );
      continue;
    }

    // Horizontal Rule
    if (line === '---' || line === '***' || line === '___') {
      docChildren.push(
        new Paragraph({
          border: {
            bottom: {
              color: 'E5E7EB',
              space: 1,
              style: BorderStyle.SINGLE,
              size: 6
            }
          },
          spacing: { before: 140, after: 140 }
        })
      );
      continue;
    }

    // Blockquote
    if (line.startsWith('> ')) {
      docChildren.push(
        new Paragraph({
          spacing: { before: 100, after: 100 },
          indent: { left: 400 },
          children: [
            new TextRun({
              text: line.slice(2).trim(),
              italics: true,
              color: '4B5563',
              size: 22
            })
          ]
        })
      );
      continue;
    }

    // Unordered List
    if (line.startsWith('- ') || line.startsWith('* ')) {
      docChildren.push(
        new Paragraph({
          bullet: { level: 0 },
          spacing: { before: 40, after: 40 },
          children: parseInlineRuns(line.slice(2).trim())
        })
      );
      continue;
    }

    // Ordered List
    const olMatch = line.match(/^(\d+)\.\s+(.*)$/);
    if (olMatch) {
      docChildren.push(
        new Paragraph({
          spacing: { before: 40, after: 40 },
          children: [
            new TextRun({ text: `${olMatch[1]}. `, bold: true, size: 23 }),
            ...parseInlineRuns(olMatch[2].trim())
          ]
        })
      );
      continue;
    }

    // Code block marker (skip the backticks line)
    if (line.startsWith('```')) {
      continue;
    }

    // Standard Paragraph
    docChildren.push(
      new Paragraph({
        spacing: { before: 60, after: 140, line: 280 },
        children: parseInlineRuns(line)
      })
    );
  }

  flushTable();

  // Build the complete docx Document
  const doc = new Document({
    styles: {
      default: {
        document: {
          run: {
            font: 'Arial',
            size: 23 // 11.5pt
          }
        }
      }
    },
    sections: [
      {
        properties: {
          page: {
            margin: {
              top: 1440, // 1 inch
              right: 1440,
              bottom: 1440,
              left: 1440
            }
          }
        },
        children: docChildren
      }
    ]
  });

  return Packer.toBlob(doc);
}

export async function exportPaperToDocx(options: DocxExportOptions): Promise<void> {
  const blob = await createPaperDocx(options);
  const blobUrl = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = blobUrl;
  anchor.download = `${(options.filename || 'paper').replace(/[/\\?%*:|"<>]/g, '_')}.docx`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(blobUrl);
}
