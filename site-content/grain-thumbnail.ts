import h from "@macrostrat/hyper";
import { useAPIHelpers } from "@macrostrat/ui-components";
import { APIV2Context, useAPIv2Result } from "sparrow/api-v2";
import "./main.styl";

function GrainThumbnail({ uuid, size = 100 }) {
  const { buildURL } = useAPIHelpers(APIV2Context);
  const dimensions = { width: size, height: size };

  let content = h("p", "No grain image");
  if (uuid != null) {
    content = h("img", {
      ...dimensions,
      src: buildURL(`/grain-image/${uuid}.jpg`),
    });
  }
  return h("div.grain-thumbnail", { style: dimensions }, content);
}

function SampleThumbnail({ sample_id, size = 100 }) {
  /** Find and render a thumbnail image given a sample id */
  if (sample_id == null) return null;
  const res = useAPIv2Result("/grain-image", { sample_id });
  const uuid = res?.[0]?.uuid;
  return h(GrainThumbnail, { uuid, size });
}

export function PageGrainThumbnail({ data: sample, defaultContent }) {
  return h(SampleThumbnail, { sample_id: sample.id, size: 150 });
}

export function SampleCard({ data: sample, defaultContent }) {
  if (sample.material != "zircon") return defaultContent;
  return h("div.grain-sample-card", [
    defaultContent,
    h(SampleThumbnail, { sample_id: sample.id }),
  ]);
}
