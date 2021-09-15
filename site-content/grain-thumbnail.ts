import h from "@macrostrat/hyper";
import { useAPIHelpers } from "@macrostrat/ui-components";
import { APIV2Context, useAPIv2Result } from "sparrow/api-v2";
import "./main.styl";

function GrainThumbnailImage({ uuid, ...rest }) {
  if (uuid == null) return null;
  const { buildURL } = useAPIHelpers(APIV2Context);

  return h("img", {
    src: buildURL(`/grain-image/${uuid}.jpg`),
    ...rest,
  });
}

function GrainThumbnail({ uuid, size = 100, fallback = null }) {
  /** Render a thumbnail with optional fallback */
  const dimensions = { width: size, height: size };

  let content = fallback;
  if (uuid != null) {
    content = h(GrainThumbnailImage, { uuid, ...dimensions });
  }
  if (content == null) {
    return null;
  }
  return h("div.grain-thumbnail", { style: dimensions }, content);
}

function SampleThumbnail({ sample_id, ...rest }) {
  /** Find and render a thumbnail image given a sample id */
  if (sample_id == null) return null;
  const res = useAPIv2Result("/grain-image", { sample_id });
  const uuid = res?.[0]?.uuid;
  return h(GrainThumbnail, { uuid, ...rest });
}

export function PageGrainThumbnail({ data, defaultContent }) {
  const { dataFile, sample } = data;
  if (dataFile != null) {
    console.log(dataFile);
    // Type is not present for now, so we make do
    if (!dataFile.basename.endsWith(".tif")) return defaultContent;
    return h(GrainThumbnail, { uuid: dataFile.file_hash, size: 150 });
  }
  return h(SampleThumbnail, { sample_id: sample.id, size: 150 });
}

export function SampleCard({ data: sample, defaultContent }) {
  if (sample.material != "zircon") return defaultContent;
  return h("div.grain-card", [
    defaultContent,
    h(SampleThumbnail, {
      sample_id: sample.id,
      fallback: h("p", "No grain image"),
    }),
  ]);
}

export function DataFileCard({ data, defaultContent }) {
  const { dataFile } = data;

  // Type is not present for now, so we make do
  if (!dataFile.basename.endsWith(".tif")) return defaultContent;

  return h("div.grain-card", [
    defaultContent,
    h(GrainThumbnail, {
      uuid: dataFile.file_hash,
      fallback: h("p", "No grain image"),
    }),
  ]);
}

export function SampleLink({ data, defaultContent }) {
  const { sample } = data;
  if (sample.material != "zircon") return defaultContent;
  return h("div.grain-link", [
    h("div.main-content", null, defaultContent),
    h(SampleThumbnail, { sample_id: sample.id, size: 40 }),
  ]);
}

export function DataFileLink({ data, defaultContent }) {
  const { dataFile } = data;
  if (!dataFile.basename.endsWith(".tif")) return defaultContent;
  return h("div.grain-link", [
    h("div.main-content", null, defaultContent),
    h(GrainThumbnail, { uuid: dataFile.file_hash, size: 40 }),
  ]);
}
