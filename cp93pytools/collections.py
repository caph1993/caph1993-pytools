import heapq
from typing import Any, Dict, List, Tuple, Union
'''
Some functions are copied from heapq
because they start with underscore and may
be eliminated in the future
'''


def _heappop_max(heap):
    """Maxheap version of a heappop."""
    lastelt = heap.pop()  # raises appropriate IndexError if heap is empty
    if heap:
        returnitem = heap[0]
        heap[0] = lastelt
        _siftup_max(heap, 0)
        return returnitem
    return lastelt


def _siftdown_max(heap, startpos, pos):
    'Maxheap variant of _siftdown'
    newitem = heap[pos]
    # Follow the path to the root, moving parents down until finding a place
    # newitem fits.
    while pos > startpos:
        parentpos = (pos - 1) >> 1
        parent = heap[parentpos]
        if parent < newitem:
            heap[pos] = parent
            pos = parentpos
            continue
        break
    heap[pos] = newitem


def _heapify_max(x):
    """Transform list into a maxheap, in-place, in O(len(x)) time."""
    n = len(x)
    for i in reversed(range(n // 2)):
        _siftup_max(x, i)


def _siftup_max(heap, pos):
    'Maxheap variant of _siftup'
    endpos = len(heap)
    startpos = pos
    newitem = heap[pos]
    # Bubble up the larger child until hitting a leaf.
    childpos = 2 * pos + 1  # leftmost child position
    while childpos < endpos:
        # Set childpos to index of larger child.
        rightpos = childpos + 1
        if rightpos < endpos and not heap[rightpos] < heap[childpos]:
            childpos = rightpos
        # Move the larger child up.
        heap[pos] = heap[childpos]
        pos = childpos
        childpos = 2 * pos + 1
    # The leaf at pos is empty now.  Put newitem there, and bubble it up
    # to its final resting place (by sifting its parents down).
    heap[pos] = newitem
    _siftdown_max(heap, startpos, pos)


Comparable = Any


class MinHeap(List[Comparable]):

    def _heappop(self):
        return heapq.heappop(self)

    def _heappush(self, elem: Comparable):
        heapq.heappush(self, elem)

    def _heapify(self):
        heapq.heapify(self)


class MaxHeap(List[Comparable]):

    def _heappop(self):
        return _heappop_max(self)

    def _heappush(self, elem: Comparable):
        self.append(elem)
        _siftdown_max(self, 0, len(self) - 1)

    def _heapify(self):
        _heapify_max(self)


Heap = Union[MinHeap, MaxHeap]


class _HeapDict(Dict[Any, Comparable]):
    '''
    Parent class for MinDict and MaxDict.
    Supports O(log n) lookup or elimination of heap root.
    '''
    heapsize_ignore_until = 200
    heapsize_max_factor = 4
    heap_class = MinHeap

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._heap: Heap = self.heap_class()
        self._init_heap()

    def _init_heap(self):
        elems = [(v, k) for k, v in self.items()]
        self._heap[:] = elems
        self._heap._heapify()

    def __setitem__(self, key: Any, value: Comparable):
        curr = self.get(key)
        found = (curr is not None) or (key in self)
        if not found or curr != value:
            super().__setitem__(key, value)
        if found and curr != value:
            self._heap._heappush((value, key))
            self._clean_heap()

    def _get_root(self):
        self._clean_heap()
        value, key = self._heap[0]
        assert self[key] == value
        return (key, value)

    def _pop_root(self):
        self._clean_heap()
        value, key = self._heap._heappop()
        assert self[key] == value
        del self[key]
        return (key, value)

    def _clean_heap(self):
        while len(self._heap):
            value, key = self._heap[0]
            curr = self.get(key)
            found = (curr is not None) or (key in self)
            if found and curr == value:
                break
            self._heap._heappop()

        too_large = max(
            self.heapsize_max_factor * len(self),
            self.heapsize_ignore_until,
        )
        if len(self._heap) > too_large:
            self._init_heap()


class MinDict(_HeapDict):
    '''
    Dictionary supporting O(log n) lookup or elimination
    of key with minimum value.
    '''
    heapsize_ignore_until = 200
    heapsize_max_factor = 4
    heap_class = MinHeap

    def get_min(self):
        return self._get_root()

    def pop_min(self):
        return self._pop_root()


class MaxDict(_HeapDict):
    '''
    Dictionary supporting O(log n) lookup or elimination
    of key with maximum value.
    '''
    heapsize_ignore_until = 200
    heapsize_max_factor = 4
    heap_class = MaxHeap

    def get_max(self):
        return self._get_root()

    def pop_max(self):
        return self._pop_root()
