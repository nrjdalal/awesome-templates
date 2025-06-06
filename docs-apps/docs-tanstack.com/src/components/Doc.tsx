import { DocTitle } from '~/components/DocTitle'
import { Markdown } from '~/components/Markdown'
import { marked } from 'marked'
import markedAlert from 'marked-alert'
import { getHeadingList, gfmHeadingId } from 'marked-gfm-heading-id'
import * as React from 'react'
import { FaEdit } from 'react-icons/fa'
import { twMerge } from 'tailwind-merge'
import { GadLeader } from './GoogleScripts'
import { Toc } from './Toc'
import { TocMobile } from './TocMobile'

type DocProps = {
  isBlog?: boolean
  title: string
  content: string
  repo: string
  branch: string
  filePath: string
  shouldRenderToc?: boolean
  colorFrom?: string
  colorTo?: string
}

export function Doc({
  isBlog = false,
  title,
  content,
  repo,
  branch,
  filePath,
  shouldRenderToc = false,
  colorFrom,
  colorTo,
}: DocProps) {
  const { markup, headings } = React.useMemo(() => {
    const markup = marked.use(
      { gfm: true },
      gfmHeadingId(),
      markedAlert(),
    )(content) as string

    const headings = getHeadingList()

    return { markup, headings }
  }, [content])

  const isTocVisible = shouldRenderToc && headings && headings.length > 1

  const markdownContainerRef = React.useRef<HTMLDivElement>(null)
  const [activeHeadings, setActiveHeadings] = React.useState<Array<string>>([])

  const headingElementRefs = React.useRef<
    Record<string, IntersectionObserverEntry>
  >({})

  React.useEffect(() => {
    const callback = (headingsList: Array<IntersectionObserverEntry>) => {
      headingElementRefs.current = headingsList.reduce(
        (map, headingElement) => {
          map[headingElement.target.id] = headingElement
          return map
        },
        headingElementRefs.current,
      )

      const visibleHeadings: Array<IntersectionObserverEntry> = []
      Object.keys(headingElementRefs.current).forEach((key) => {
        const headingElement = headingElementRefs.current[key]
        if (headingElement.isIntersecting) {
          visibleHeadings.push(headingElement)
        }
      })

      if (visibleHeadings.length >= 1) {
        setActiveHeadings(visibleHeadings.map((h) => h.target.id))
      }
    }

    const observer = new IntersectionObserver(callback, {
      rootMargin: '0px',
      threshold: 0.2,
    })

    const headingElements = Array.from(
      markdownContainerRef.current?.querySelectorAll(
        'h2[id], h3[id], h4[id], h5[id], h6[id]',
      ) ?? [],
    )
    headingElements.forEach((el) => observer.observe(el))

    return () => observer.disconnect()
  }, [])

  return (
    <React.Fragment>
      {shouldRenderToc ? <TocMobile headings={headings} /> : null}
      <div
        className={twMerge(
          'mx-auto flex w-full bg-white/70 dark:bg-black/40',
          isTocVisible && 'max-w-full',
          shouldRenderToc && 'lg:pt-0',
        )}
      >
        <div
          className={twMerge(
            'ml-auto flex w-full max-w-[820px] flex-col overflow-auto p-4.5',
            isBlog && 'mx-auto',
          )}
        >
          <GadLeader />
          {title ? <DocTitle>{title}</DocTitle> : null}
          <div className="h-4" />
          <div className="h-px bg-gray-500/20" />
          <div className="h-4" />
          <div
            ref={markdownContainerRef}
            className={twMerge(
              'prose prose-gray prose-sm prose-p:leading-7 dark:prose-invert max-w-none',
              isTocVisible && 'pr-4 lg:pr-6',
              'styled-markdown-content',
            )}
          >
            <Markdown htmlMarkup={markup} />
          </div>
          <div className="h-12" />
          <div className="h-px w-full bg-gray-500 opacity-30" />
          <div className="py-4 opacity-70">
            <a
              href={`https://github.com/${repo}/edit/${branch}/${filePath}`}
              className="flex items-center gap-2"
            >
              <FaEdit /> Edit on GitHub
            </a>
          </div>
          <div className="h-24" />
        </div>

        {isTocVisible ? (
          <div className="hidden w-full max-w-64 border-l border-gray-500/20 transition-all 2xl:block">
            <Toc
              headings={headings}
              activeHeadings={activeHeadings}
              colorFrom={colorFrom}
              colorTo={colorTo}
            />
          </div>
        ) : (
          <div
            className={twMerge(
              'hidden w-full max-w-64 2xl:block',
              isBlog && '2xl:hidden',
            )}
          />
        )}
      </div>
    </React.Fragment>
  )
}
