import {Markdown} from '@macrostrat/ui-components'
import aboutText from './about.md'
import h from '@macrostrat/hyper'
import { PageGrainThumbnail, SampleCard } from './grain-thumbnail'

export default {
  landingText: h(Markdown, { src: aboutText }),
  sampleHeaderInfo: PageGrainThumbnail,
  sampleCardContent: SampleCard

  //shortSiteTitle: "ALC"
  // sessionCardContent: ({data})-> h(DZSessionData, data),
  // dataFilePage: ({data})->
  //   {file_hash} = data
  //   h(DataSheetCard, {uuid: file_hash})
}
