import { useCallback, useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import { api } from '../api/client';
import type { GraphResponse } from '../types/api';

const NODE_COLORS: Record<string, string> = {
  MOVIE: '#e07a5f',
  CLUSTER: '#81b29a',
  GENRE: '#f2cc8f',
  RATING: '#3d405b',
  default: '#888',
};

type Props = {
  movieId: string;
  movieTitle: string;
  onClose: () => void;
};

export function KnowledgeGraphPanel({ movieId, movieTitle, onClose }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<{ label: string; examples: { text: string; source: string }[] } | null>(null);

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getGraph(movieId);
      setGraph(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load graph');
      setGraph(null);
    } finally {
      setLoading(false);
    }
  }, [movieId]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  useEffect(() => {
    if (!graph || !containerRef.current || graph.nodes.length === 0) return;

    const elements = [
      ...graph.nodes.map((n) => ({
        group: 'nodes' as const,
        data: { ...n.data, id: n.data.id },
      })),
      ...graph.edges.map((e) => ({
        group: 'edges' as const,
        data: {
          ...e.data,
          id: e.data.id,
        },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            width: 24,
            height: 24,
            'background-color': (node) =>
              NODE_COLORS[node.data('type') as string] ?? NODE_COLORS.default,
            'border-width': 1,
            'border-color': 'rgba(255,255,255,0.2)',
            label: 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'font-size': '11px',
            color: '#e4e4de',
            'text-outline-color': '#0d0d0d',
            'text-outline-width': 3,
            'text-max-width': '80px',
            'text-wrap': 'ellipsis',
          },
        },
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            'target-arrow-color': '#555',
            'target-arrow-shape': 'triangle',
            'line-color': '#444',
            width: 1.2,
            label: 'data(label)',
            'font-size': '9px',
            color: '#888',
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: false,
        idealEdgeLength: 120,
        nodeOverlap: 20,
        nodeRepulsion: 8000,
        padding: 40,
      },
    });

    cy.on('tap', 'node', (ev) => {
      const node = ev.target;
      const nodeData = node.data();
      const examples = nodeData.examples as { text: string; source: string }[] | undefined;
      if (Array.isArray(examples) && examples.length > 0) {
        const label = (nodeData.label as string) ?? 'Cluster';
        setEvidence({ label, examples });
      } else {
        setEvidence(null);
      }
    });

    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [graph, movieId]);

  const hasGraph = graph && graph.nodes.length > 0;

  return (
    <div className="knowledge-graph-overlay" role="dialog" aria-label="Knowledge Graph">
      <div className="knowledge-graph-panel">
        <div className="knowledge-graph-header">
          <h2>Knowledge Graph: {movieTitle}</h2>
          <button type="button" className="knowledge-graph-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        {loading ? (
          <p>Loading graph...</p>
        ) : error ? (
          <p className="error">{error}</p>
        ) : !hasGraph ? (
          <div className="knowledge-graph-ingest">
            <p>Run analysis on this movie to see the complaint graph (clusters, ratings, genre).</p>
          </div>
        ) : (
          <div className="knowledge-graph-content">
            <div className="knowledge-graph-cy-wrap">
              <div ref={containerRef} className="knowledge-graph-cy" />
            </div>
            <div className="knowledge-graph-evidence-wrap">
              {evidence ? (
                <div className="knowledge-graph-evidence">
                  <h3>{evidence.label}</h3>
                  {evidence.examples.map((ex, i) => (
                    <p key={i}>
                      <em>({ex.source})</em> {ex.text}
                    </p>
                  ))}
                </div>
              ) : (
                <div className="knowledge-graph-evidence-placeholder">
                  Click a complaint theme to see example reviews
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
