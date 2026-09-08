import MarkdownIt from 'markdown-it'
const parser = new MarkdownIt({html:false,linkify:false,typographer:false,breaks:true})
parser.disable('image')
const defaultLink=parser.renderer.rules.link_open
parser.renderer.rules.link_open=(tokens,index,options,env,self)=>{
  const token=tokens[index]; token.attrSet('target','_blank'); token.attrSet('rel','noopener noreferrer')
  return defaultLink ? defaultLink(tokens,index,options,env,self) : self.renderToken(tokens,index,options)
}
export function renderMarkdown(content:string) { return parser.render(content) }

