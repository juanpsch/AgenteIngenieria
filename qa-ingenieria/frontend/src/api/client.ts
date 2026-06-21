// Cliente HTTP tipado contra el contrato §7 (proxied a /api por Vite).

export type CheckState = "pass" | "fail" | "warn" | "info";
export interface Check {
  dimension: "identidad" | "completitud";
  label: string;
  state: CheckState;
  detail?: string;
  requerido?: boolean;
  // metadata de regla (para el feedback: proponer variante)
  campo?: string;
  patron?: string;
  valor?: string;
  regla_tipo?: string;
}
export interface VarianteSugerida {
  campo: string; patron: string; ok: boolean; error?: boolean;
  cubre: number; total: number; matchea_negativos: number; ejemplos_si: number; ejemplos_no: number;
}
export type Veredicto = "valido" | "revision_manual" | "invalido" | "faltan_datos";
export interface BBox { x: number; y: number; w: number; h: number; }
export interface ScoreDetalle {
  score: number | null;
  cajetin: number | null;
  pagina: number | null;
  peso_cajetin: number;
  peso_pagina: number;
  umbral_aprobacion: number;
  umbral_revision: number;
  umbrales_auto: boolean;
  n_referencias: number;
  ref_top: { filename: string | null; score: number | null } | null;
  decisivo: boolean;
  n_negativos?: number;             // contra-ejemplos (docs rechazados por el humano)
  negativos?: number | null;        // cuánto se parece a un negativo (0–100)
  score_positivos?: number | null;  // score contra positivos ANTES de penalizar
}
export type ZonaClase = "identidad" | "visual" | "regla";
export interface ZonaResultado {
  nombre: string;
  pagina: number;
  bbox: BBox | null;
  clase: ZonaClase;
  estado: CheckState;
  detalle?: string;
  score?: number | null;
  requerido?: boolean;
  campo?: string;
  valor?: string | null;
}
// --- Revisión de contenido (Fase 1) ---
export type Severidad = "bloqueante" | "mayor" | "menor" | "observacion";
export type EstadoRevision = "ok" | "advertencia" | "fallo" | "no_verificable";
export type DimensionRev = "legibilidad" | "norma" | "contenido" | "consistencia";
export type VerdictoRevision = "aprobado" | "aprobado_con_notas" | "observado" | "rechazado" | "pendiente_senior";
export interface Hallazgo {
  check_id: string;
  dimension: DimensionRev;
  severidad: Severidad;
  estado: EstadoRevision;
  ubicacion?: { pagina: number; bbox?: BBox | null };
  evidencia?: string;
  razonamiento: string;
  sugerencia?: string;
  fuente: "deterministico" | "reglas" | "vlm";
  norma_ref?: string;
  req_id?: string;
  estado_previo?: EstadoRevision;   // estado por texto antes de que el VLM verificara la regla
  nota_vlm?: string;                // qué concluyó el VLM (por qué cambió la regla)
}
export type Juicio = "de_acuerdo" | "no_aplica" | "regla_mal";
export interface CatalogoRequisito {
  req_id: string; id: string; tipo: string; descripcion?: string; severidad?: string;
  norma_id: string; norma_nombre?: string; norma_ref?: string; disciplinas?: string[] | null;
}
export interface SugerenciaReq {
  req_id: string; descripcion: string; norma_ref?: string; severidad?: string;
  motivo: string; evidencia: string; n?: number; total?: number;
}
export interface SugerenciasRequisitos {
  agregar: SugerenciaReq[]; quitar: SugerenciaReq[]; prior_disciplina: SugerenciaReq[];
}
export interface Perfil {
  id: string; nombre: string; proyecto?: string | null; jurisdiccion?: string | null; requisitos: string[];
}
export interface RevisionBlock {
  verdicto: VerdictoRevision | null;
  severidad_max: string | null;
  confiabilidad: string | null;
  resuelta: boolean;
  notas: string | null;
  hallazgos: Hallazgo[];
}
export interface ValidarResp {
  thread_id: string;
  status: string;
  veredicto: Veredicto;
  tipo_doc: string;
  score: number | null;
  no_concluyente: boolean;
  score_detalle: ScoreDetalle | null;
  maturity: string | null;
  cajetin_bbox: BBox | null;
  resumen: string;
  checks: Check[];
  campos?: Record<string, unknown>;
  zonas_resultado: ZonaResultado[];
  revision: RevisionBlock | null;
  requisito_feedback: Record<string, { juicio: Juicio; nota: string | null }>;
  imagen: string | null;
  imagenes: string[];
  n_paginas: number;
  documento_panel: { titulo?: string; [k: string]: unknown } | null;
}
export interface Tipo {
  tipo_doc: string; nombre: string; empresa?: string | null;
  disciplinas: string[]; refs_count: number; maturity: string; actualizado?: string | null;
}
export interface Referencia { ref_id: string; filename: string; origin: string; }
export interface Cobertura { campo: string; patron: string; n: number; total: number; error?: boolean; }
export type RuleTipo = "regex" | "filename" | "presencia";
export interface Zona {
  nombre: string;
  pagina?: number;
  bbox: BBox;
  identidad?: boolean;
  campo?: string;
  patron?: string;
  tipo?: RuleTipo;
  requerido?: boolean;
  ancla_inicio?: string;
  ancla_fin?: string;
  comparar?: "texto" | "visual";
}
export interface HistItem {
  thread_id: string; doc: string; tipo_doc: string; status: string;
  veredicto: Veredicto; score: number | null; operador: string; fecha: string;
  decision: string | null; promovido_a_ref: number;
}
export interface Historial { items: HistItem[]; metricas: { validados: number; aprobacion_pct: number; pendientes: number; promovidos: number }; }

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const opts: RequestInit = { method, headers: {} };
  if (body !== undefined) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(`/api${path}`, opts);
  if (!r.ok) throw new Error((await r.text().catch(() => "")) || `${r.status}`);
  return r.json() as Promise<T>;
}

async function form<T>(path: string, fd: FormData): Promise<T> {
  const r = await fetch(`/api${path}`, { method: "POST", body: fd });
  if (!r.ok) throw new Error((await r.text().catch(() => "")) || `${r.status}`);
  return r.json() as Promise<T>;
}

export const api = {
  validar(file: File, tipo_doc: string, extra: { proyecto?: string; disciplina?: string; texto?: string; thread_id?: string; revisar?: boolean } = {}) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("tipo_doc", tipo_doc);
    if (extra.revisar === false) fd.append("revisar", "false");  // toggle de revisión de contenido
    for (const [k, v] of Object.entries(extra)) if (typeof v === "string" && v) fd.append(k, v);
    return form<ValidarResp>("/validar", fd);
  },
  listTipos: () => req<Tipo[]>("GET", "/tipos"),
  getTipo: (id: string) => req<any>("GET", `/tipos/${id}`),
  capturar(file: File, tipo_doc?: string, nombre?: string, modo = "ejemplo") {
    const fd = new FormData();
    fd.append("file", file); fd.append("modo", modo);
    if (tipo_doc) fd.append("tipo_doc", tipo_doc);
    if (nombre) fd.append("nombre", nombre);
    return form<{ template: any; yaml: string }>("/tipos/capturar", fd);
  },
  capturarMulti(files: File[], tipo_doc?: string, nombre?: string, modo = "ejemplo") {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("modo", modo);
    if (tipo_doc) fd.append("tipo_doc", tipo_doc);
    if (nombre) fd.append("nombre", nombre);
    return form<{ template: any; yaml: string; cobertura: Cobertura[] }>("/tipos/capturar-multi", fd);
  },
  putTipo: (id: string, yaml: string) => req("PUT", `/tipos/${id}`, { yaml }),
  delTipo: (id: string) => req("DELETE", `/tipos/${id}`),
  addRef(id: string, file: File) { const fd = new FormData(); fd.append("file", file); return form<any>(`/tipos/${id}/referencias`, fd); },
  delRef: (id: string, refId: string) => req("DELETE", `/tipos/${id}/referencias/${refId}`),
  refPreviewUrl: (id: string, refId: string, page = 1) => `/api/tipos/${id}/referencias/${refId}/preview?page=${page}`,
  delNeg: (id: string, refId: string) => req("DELETE", `/tipos/${id}/negativos/${refId}`),
  negPreviewUrl: (id: string, refId: string, page = 1) => `/api/tipos/${id}/negativos/${refId}/preview?page=${page}`,
  putZonas: (id: string, zonas: Zona[]) => req<{ ok: boolean; zonas: Zona[]; refs_reembebidas: number; maturity: string }>("PUT", `/tipos/${id}/zonas`, { zonas }),
  zonaSugerida: (id: string) => req<{ zona: BBox }>("GET", `/tipos/${id}/zona-sugerida`),
  sugerirVariante: (id: string, campo: string, valor: string) => req<VarianteSugerida>("POST", `/tipos/${id}/reglas/sugerir-variante`, { campo, valor }),
  aplicarRegla: (id: string, campo: string, patron: string) => req<{ ok: boolean }>("POST", `/tipos/${id}/reglas/aplicar`, { campo, patron }),
  getCaso: (threadId: string) => req<ValidarResp & { decision: string | null }>("GET", `/casos/${threadId}`),
  decision: (threadId: string, decision: "approved" | "rejected") => req<any>("POST", `/casos/${threadId}/decision`, { decision }),
  agregarNegativo: (threadId: string) => req<{ negativos_count: number }>("POST", `/casos/${threadId}/negativo`),
  revisarCaso: (threadId: string) => req<ValidarResp & { decision: string | null }>("POST", `/casos/${threadId}/revisar`),
  casoPaginaUrl: (threadId: string, page = 1) => `/api/casos/${threadId}/pagina/${page}`,  // preview on-demand (no payload)
  casoArchivoUrl: (threadId: string) => `/api/casos/${threadId}/archivo`,  // doc original inline (visor nativo)
  buscarEnCaso: (threadId: string, q: string) =>
    req<{ pagina: number; rects: BBox[] }[]>("GET", `/casos/${threadId}/buscar?q=${encodeURIComponent(q)}`),
  revisionDecision: (threadId: string, decision: VerdictoRevision | "escalar_senior", notas?: string) =>
    req<{ verdicto: string; resuelta: boolean }>("POST", `/casos/${threadId}/revision/decision`, { decision, notas }),
  revisionVlm: (threadId: string) => req<RevisionBlock>("POST", `/casos/${threadId}/revision/vlm`),
  catalogoRequisitos: () => req<CatalogoRequisito[]>("GET", "/normas/catalogo"),
  putRequisitos: (id: string, requisitos: string[]) =>
    req<{ ok: boolean; requisitos_resueltos: string[] }>("PUT", `/tipos/${id}/requisitos`, { requisitos }),
  sugerenciasRequisitos: (id: string) => req<SugerenciasRequisitos>("GET", `/tipos/${id}/requisitos/sugerencias`),
  perfiles: () => req<Perfil[]>("GET", "/perfiles"),
  requisitoFeedback: (threadId: string, requisito_id: string, juicio: Juicio, notas?: string) =>
    req<{ ok: boolean }>("POST", `/casos/${threadId}/requisito-feedback`, { requisito_id, juicio, notas }),
  promover: (id: string, threadId: string, promote: boolean) => req<any>("POST", `/tipos/${id}/referencias/promover`, { thread_id: threadId, promote }),
  entregas: () => req<Record<string, string[]>>("GET", "/entregas-tipo"),
  putEntrega: (id: string, documentos_requeridos: string[]) => req("PUT", `/entregas-tipo/${id}`, { documentos_requeridos }),
  delEntrega: (id: string) => req("DELETE", `/entregas-tipo/${id}`),
  disciplinas: () => req<string[]>("GET", "/disciplinas"),
  addDisciplina: (nombre: string) => req<string[]>("POST", "/disciplinas", { nombre }),
  delDisciplina: (nombre: string) => req<string[]>("DELETE", `/disciplinas/${nombre}`),
  proyectos: () => req<{ id: string; nombre: string }[]>("GET", "/proyectos"),
  historial: () => req<Historial>("GET", "/historial"),
};
