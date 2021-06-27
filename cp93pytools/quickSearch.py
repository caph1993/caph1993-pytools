from collections import defaultdict
from typing import DefaultDict, List, Sequence, Tuple


class quickFilter:
  """
  custom fuzzy filter that uses 1,2,3-grams to filter and sort
  several strings by their similarity with a given pattern
  """
  _elements: Sequence[str]
  _ngrams:   DefaultDict[str, Sequence[Tuple[int,int]]]

  def __init__(self, elems: Sequence[str]):
    self._elements = elems
    low_elems = [s.lower() for s in elems]
    results = [
      (sub, i, score)
      for i, elem in enumerate(low_elems)
      for sub, score in self._get_grams(elem)
    ]
    best = defaultdict(lambda: defaultdict(lambda: 0))
    for sub, i, score in results:
      best[sub][i] = max(best[sub][i], score)
    ngrams = defaultdict(lambda: [])
    for (sub, i), score in best.items():
      ngrams[sub].append((i, score))
    self._ngrams = ngrams # type: ignore

  def _get_grams(self, pattern: str) -> Sequence[Tuple[str,int]]:
    '''
    Compute all 1,2,3-grams of pattern and their score, possibly repeating.
    The output size is bounded by 3*len(pattern)
    Additional score is given if the gram comes after space, dash or underscore.
    '''
    n = len(pattern)
    out = []
    for i in range(n):
      isStart = (i==0) or (pattern[i-1] in (' ', '-', '_'))
      for j in range(i+1, min(i+3, n)):
        sub = pattern[i:j]
        score = 1 + isStart
        out.append((sub, score))
    return out

  def getFiltered(self, pattern:str) -> List[int]:
    '''
    Get the indices of elements that match the pattern in fuzzy manner
    '''
    if len(pattern) == 0:
      out = list(range(len(self._elements)))
    else:
      pattern = pattern.lower()
      scored = defaultdict(lambda: 0)
      for sub, _ in self._get_grams(pattern):
        for i, score in self._ngrams[sub]:
          scored[i] += score
      ranking = sorted(sorted.items(), key=(lambda _,score: -score))) # type: ignore
      threshold = max(1, len(pattern)*3-4)
      out = [i for i, score in ranking if score>threshold]
    return out


'''

package main

import (
  "fmt"
  "io/ioutil"
  "log"
  "os"
  "path/filepath"
  "sort"
  "strings"

  "fyne.io/fyne/v2"
  "fyne.io/fyne/v2/app"
  "fyne.io/fyne/v2/container"
  "fyne.io/fyne/v2/driver/desktop"
  "fyne.io/fyne/v2/widget"
)

var ShortcutAltUp = desktop.CustomShortcut{KeyName: fyne.KeyUp, Modifier: desktop.AltModifier}
var ShortcutCtrlBackspace = desktop.CustomShortcut{KeyName: fyne.KeyBackspace, Modifier: desktop.ControlModifier}

type escapeEntry struct {
  widget.Entry
  onEnter        func()
  onArrowUp      func()
  onArrowDown    func()
  onAltArrowUp   func()
  onAltArrowDown func()
}

func (e *escapeEntry) onEsc() {
  fmt.Println(e.Entry.Text)
  e.Entry.SetText("")
}

func newEscEntry() *escapeEntry {
  entry := &escapeEntry{}
  entry.ExtendBaseWidget(entry)
  return entry
}

func (e *escapeEntry) TypedKey(key *fyne.KeyEvent) {
  switch key.Name {
  case fyne.KeyEscape:
    e.onEsc()
  case fyne.KeyReturn:
    e.onEnter()
  case fyne.KeyUp:
    e.onArrowUp()
  case fyne.KeyDown:
    e.onArrowDown()
  default:
    e.Entry.TypedKey(key)
  }
}
func (e *escapeEntry) TypedShortcut(s fyne.Shortcut) {
  if _, ok := s.(*desktop.CustomShortcut); !ok {
    e.Entry.TypedShortcut(s)
    return
  }
  name := s.ShortcutName()
  switch name {
  case ShortcutAltUp.ShortcutName():
    e.onAltArrowUp()
  case ShortcutCtrlBackspace.ShortcutName():
    e.Entry.SetText("")
  default:
    log.Println("Shortcut typed:", name)
  }
}

type myPath struct {
  info      os.FileInfo
  name      string
  path      string
  resolved  string
  isSymlink bool
  isDir     bool
  icon      string
}

func newMyPath(cwd, name string) *myPath {
  e := new(myPath)
  e.name = name
  e.path = fmt.Sprintf("%s/%s", cwd, name)
  info, _ := os.Lstat(e.path)
  e.info = info
  resolved, err := filepath.EvalSymlinks(e.path)
  e.resolved = resolved
  rinfo, err := os.Lstat(resolved)
  e.isDir = (err == nil) && rinfo.IsDir()
  e.isSymlink = (e.path != resolved)
  e.icon = "f"
  if e.isDir {
    e.icon = "D"
  }
  if e.isSymlink {
    e.icon = "s" + e.icon
  }
  e.icon = fmt.Sprintf("[%s]", e.icon)
  return e
}

type dirList struct {
  wPwd     *widget.Button
  wCwd     *widget.Label
  wFilter  *escapeEntry
  wVBox    *fyne.Container
  objects  []*widget.Label
  filter   *quickFilter
  root     string
  complete []string
  filtered []int
  shown    []int
  nshown   int
  offset   int
  fileInfo map[string]*myPath
  selected int
}

func NewDirList(root string) *dirList {
  e := new(dirList)
  e.nshown = 10
  e.wCwd = widget.NewLabel("")
  e.wPwd = widget.NewButton("Parent (alt+up)", e.enterParent)
  e.wFilter = newEscEntry()
  e.wFilter.Entry.SetPlaceHolder("Filter...")
  e.wFilter.Entry.OnChanged = e.applyFilter
  e.wFilter.onEnter = e.onEnter
  e.wFilter.onArrowUp = e.onArrowUp
  e.wFilter.onArrowDown = e.onArrowDown
  e.wFilter.onAltArrowUp = e.enterParent
  e.wVBox = container.NewVBox()
  e.enterDir(root)
  return e
}

func (e *dirList) enterDir(root string) {
  e.root = root
  e.wCwd.SetText(root)
  e.fileInfo = map[string]*myPath{}
  e.complete = []string{}
  files, err := ioutil.ReadDir(root)
  if err != nil {
    if root == "/" {
      log.Fatal(err)
    } else {
      e.enterDir("/")
    }
  }
  for _, file := range files {
    name := file.Name()
    e.fileInfo[name] = newMyPath(root, name)
    e.complete = append(e.complete, name)
  }
  sort.SliceStable(e.complete, func(i, j int) bool {
    return strings.ToLower(e.complete[i]) < strings.ToLower(e.complete[j])
  })
  e.filter = newQuickFilter(e.complete)
  e.wFilter.SetText("")
  e.applyFilter(e.wFilter.Text)
}

func (e *dirList) applyFilter(filter string) {
  showHidden := (len(filter) > 0 && filter[0] == '.')
  e.filtered = []int{}
  for _, i := range e.filter.getFiltered(filter) {
    name := e.complete[i]
    isHidden := (name[0] == '.')
    if !isHidden || showHidden {
      e.filtered = append(e.filtered, i)
    }
  }
  e.offset = 0
  e.selected = -1
  if len(filter) > 0 && len(e.filtered) > 0 {
    e.selected = 0
  }
  e.computeShown()
}

func (e *dirList) computeShown() {
  e.shown = []int{}
  for i := e.offset; i < len(e.filtered) && i < e.offset+e.nshown; i++ {
    e.shown = append(e.shown, e.filtered[i])
  }
  out := []fyne.CanvasObject{}
  same_out := []*widget.Label{}
  for _, ifile := range e.shown {
    name := e.complete[ifile]
    info := e.fileInfo[name]
    w := widget.NewLabel(fmt.Sprintf("%s %s", info.icon, info.name))
    out = append(out, w)
    same_out = append(same_out, w)
  }
  e.wVBox.Objects = out
  e.objects = same_out
  e.highlightSelected()
}

func (e *dirList) highlightSelected() {
  for i, obj := range e.objects {
    obj.TextStyle.Bold = (e.offset+i == e.selected)
  }
  e.wVBox.Refresh()
}

func (e *dirList) onEnter() {
  if e.selected == -1 {
    return
  }
  name := e.complete[e.filtered[e.selected]]
  info := e.fileInfo[name]
  if info.isDir {
    e.enterDir(info.path)
  } else {
    log.Print(info.path)
  }
}

func (e *dirList) enterParent() {
  root := strings.TrimRight(e.root, "/")
  seps := strings.Split(root, "/")
  seps = seps[:len(seps)-1]
  parent := strings.Join(seps, "/")
  e.enterDir(parent)
}

func (e *dirList) onArrowUp() {
  if e.selected <= -1 {
    return
  }
  e.selected = e.selected - 1
  if e.selected < e.offset && e.selected >= 0 {
    e.offset = e.offset - 1
    e.computeShown()
  }
  e.highlightSelected()
}

func (e *dirList) onArrowDown() {
  if e.selected+1 >= len(e.filtered) {
    return
  }
  e.selected = e.selected + 1
  if e.selected >= e.offset+e.nshown {
    e.offset = e.offset + 1
    e.computeShown()
  }
  e.highlightSelected()
}

func main() {
  a := app.New()
  w := a.NewWindow("Hello")

  //filter := newEscEntry()
  //filter.Entry.SetPlaceHolder("Filter...")
  //command := newEscEntry()
  //filter.Entry.SetPlaceHolder("Command...")

  root := "/home/carlos"
  dirs := NewDirList(root)

  ctrlTab := desktop.CustomShortcut{KeyName: fyne.KeyTab, Modifier: desktop.ControlModifier}
  w.Canvas().AddShortcut(&ctrlTab, func(shortcut fyne.Shortcut) {
    fmt.Println("We tapped Ctrl+Tab")
  })

  //hello := widget.NewLabel("Hello Fyne!")
  w.SetContent(container.NewVBox(
    dirs.wPwd,
    dirs.wCwd,
    dirs.wFilter,
    dirs.wVBox,
    /*widget.NewButton("Hi!", func() {
      hello.SetText("Welcome :)")
      //dirs.Objects = append(dirs.Objects, widget.NewLabel("/home"))
    }),
    */
    //hello,
  ))
  w.Canvas().Focus(dirs.wFilter)
  w.ShowAndRun()
}
'''