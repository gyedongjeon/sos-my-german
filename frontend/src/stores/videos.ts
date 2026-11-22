import { defineStore } from 'pinia'
import { api } from '../api'
import type { Video, VideoHit, VideoSuggestion, VideoSummary } from '../types'

export const LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
/** What the videos without a level are listed under, and the choice that shows every video. */
export const NO_LEVEL = 'No level'
export const ALL = 'All'

/** The videos saved to study with. */
export const useVideosStore = defineStore('videos', {
  state: () => ({
    videos: [] as VideoSummary[],
    loading: true,
    error: '',
    adding: false,
    addError: '',
    // The sentences found by the last search of the saved subtitles, and what was looked for.
    hits: [] as VideoHit[],
    searched: '',
    searching: false,
    // The level chosen on the videos page; kept while the app is open.
    level: ALL,
    // Videos like a saved one, and the saved one they were asked for.
    suggestions: [] as VideoSuggestion[],
    suggestedFor: null as number | null,
    suggesting: false,
    suggestError: '',
  }),
  getters: {
    /** The levels that have videos, easiest first, then the videos without one. */
    levels: (state): string[] => [
      ...LEVELS.filter((level) => state.videos.some((v) => v.level === level)),
      ...(state.videos.some((v) => v.level === null) ? [NO_LEVEL] : []),
    ],
    /** The chosen level, or all videos while none is chosen or it has no video left. */
    active(state): string {
      return this.levels.includes(state.level) ? state.level : ALL
    },
    shown(state): VideoSummary[] {
      if (this.active === ALL) return state.videos
      return state.videos.filter((v) => (v.level ?? NO_LEVEL) === this.active)
    },
  },
  actions: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        this.videos = await api<VideoSummary[]>('/videos')
      } catch (e) {
        this.error = (e as Error).message
      } finally {
        this.loading = false
      }
    },

    /** Saves the video a YouTube link leads to; resolves with it, or null with `addError` set. */
    async add(url: string): Promise<Video | null> {
      this.adding = true
      this.addError = ''
      try {
        const video = await api<Video>('/videos', { method: 'POST', json: { url: url.trim() } })
        if (!this.videos.some((v) => v.id === video.id)) {
          const { lines, ...about } = video
          this.videos.unshift({ ...about, sentences: lines.length })
        }
        this.suggestions = this.suggestions.filter((s) => s.video_id !== video.video_id)
        return video
      } catch (e) {
        this.addError = (e as Error).message
        return null
      } finally {
        this.adding = false
      }
    },

    /** Takes over a video's level in the list. */
    leveled(video: Video | null): Video | null {
      const listed = video && this.videos.find((v) => v.id === video.id)
      if (listed && video) listed.level = video.level
      return video
    },

    /** Sets a video's level by hand, or clears it with null. */
    async setLevel(id: number, level: string | null): Promise<Video | null> {
      this.error = ''
      try {
        return this.leveled(await api<Video>(`/videos/${id}/level`, { method: 'PUT', json: { level } }))
      } catch (e) {
        this.error = (e as Error).message
        return null
      }
    },

    /** Has a video's level estimated again from its subtitles. */
    async estimateLevel(id: number): Promise<Video | null> {
      this.error = ''
      try {
        return this.leveled(await api<Video>(`/videos/${id}/level`, { method: 'POST' }))
      } catch (e) {
        this.error = (e as Error).message
        return null
      }
    },

    /** Finds videos like a saved one, at a similar level. */
    async suggest(id: number) {
      this.suggestedFor = id
      this.suggestions = []
      this.suggestError = ''
      this.addError = ''
      this.suggesting = true
      try {
        const found = await api<VideoSuggestion[]>(`/videos/${id}/suggestions`, { method: 'POST' })
        if (this.suggestedFor === id) this.suggestions = found
      } catch (e) {
        if (this.suggestedFor === id) this.suggestError = (e as Error).message
      } finally {
        if (this.suggestedFor === id) this.suggesting = false
      }
    },

    /** Looks for a word or phrase in the subtitles of all saved videos. */
    async search(phrase: string) {
      const wanted = phrase.trim()
      this.error = ''
      this.hits = []
      this.searched = wanted
      if (!wanted) return
      this.searching = true
      try {
        this.hits = await api<VideoHit[]>(`/video-lines?q=${encodeURIComponent(wanted)}`)
      } catch (e) {
        this.error = (e as Error).message
      } finally {
        this.searching = false
      }
    },

    async remove(id: number) {
      this.error = ''
      try {
        await api(`/videos/${id}`, { method: 'DELETE' })
        this.videos = this.videos.filter((v) => v.id !== id)
        this.hits = this.hits.filter((hit) => hit.video !== id)
      } catch (e) {
        this.error = (e as Error).message
      }
    },
  },
})
