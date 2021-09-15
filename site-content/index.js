import {Markdown} from '@macrostrat/ui-components'
import aboutText from './about.md'
import h from '@macrostrat/hyper'

export default {
  landingText: h(Markdown, {src: aboutText})
  //shortSiteTitle: "ALC"
  // sessionCardContent: ({data})-> h(DZSessionData, data),
  // dataFilePage: ({data})->
  //   {file_hash} = data
  //   h(DataSheetCard, {uuid: file_hash})
}
