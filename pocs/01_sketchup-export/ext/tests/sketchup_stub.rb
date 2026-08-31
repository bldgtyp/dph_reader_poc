# ---------------------------------------------------------------------------
# A stub SketchUp API -- just enough of it to load and drive the extension
# outside SketchUp.
#
# The technique is the whole reason POC-2's Ed budget is two sessions rather
# than five: everything genuinely bug-prone in the collector -- transform
# accumulation, the `*ID` ‖ `*Auto` coalesce, nil dictionary guards,
# path-qualified ids, the census invariants, Marshal decoding -- is testable
# here, and a first live run realistically will not reconcile.
#
# ⚠ What a stub can NEVER tell you:
#
#   * `UI.start_timer` is stubbed with a plain Ruby `Thread`, which works
#     properly in stock Ruby. In SketchUp it is the reverse -- threads starve
#     and the timer works. That inversion is the whole reason the real code is
#     shaped as it is, and no test here can see it.
#   * whether designPH's real models look like the trees built here. They are
#     hand-made, and *a synthetic model is not evidence about real models* --
#     a six-face test model already produced one confidently wrong schema rule
#     on this project. The reconciliation against the Phase 0/1 corpus
#     baselines is what carries evidential weight; this carries none.
#
# Ruby 2.7 (SketchUp 2022's). `ruby -c` before installing anything.
# ---------------------------------------------------------------------------
require "tmpdir"

STUB_LOAD_DIR = Dir.mktmpdir("dphplus-stub")
File.write(File.join(STUB_LOAD_DIR, "sketchup.rb"), "")
$LOAD_PATH.unshift(STUB_LOAD_DIR)

MF_CHECKED = 1 unless defined?(MF_CHECKED)
MF_UNCHECKED = 0 unless defined?(MF_UNCHECKED)

module UI
  # A plain Ruby Thread stands in for SketchUp's main-thread timer. Correct
  # here, wrong in SketchUp -- see the header.
  def self.start_timer(interval, repeat = false, &block)
    Thread.new do
      loop do
        sleep(interval)
        block.call
        break unless repeat
      end
    end
  end

  def self.stop_timer(handle)
    handle.kill if handle.respond_to?(:kill)
  end

  def self.menu(_name)
    Menu.new
  end

  # Recorded, not just printed. "Every failure class lands as a visible verdict"
  # (POC-4 §2) is only testable if the test can read what the user would see.
  def self.messagebox(text)
    (@messages ||= []) << text
    puts "[messagebox] #{text.split("\n").first}"
    nil
  end

  class << self
    attr_reader :messages

    def reset_messages
      @messages = []
    end
  end

  # The real one returns the chosen path, or **nil** when the user cancels.
  # Cancelling is a normal outcome, not an error, and the extension has to say
  # so rather than write somewhere the user did not choose.
  def self.savepanel(_title, directory, filename)
    File.join(directory.to_s, filename.to_s)
  end

  class Menu
    def add_submenu(_name)
      self
    end

    def add_item(_name)
      :menu_item
    end

    def add_separator; end

    def set_validation_proc(_item, &_block); end
  end

  # Enough of `HtmlDialog` to drive the Ruby half of the bridge from a test.
  #
  # ⚠ It carries no CEF, so it proves nothing about the two things that actually
  # bite there: the payload ceiling on `execute_script`, and the fact that
  # SketchUp drives CEF from the main run loop (hard rule 9). What it does prove
  # is the wiring — which action was dispatched, with what payload, and what the
  # user is shown when something refuses or raises.
  class HtmlDialog
    STYLE_DIALOG = 0

    attr_reader :options, :callbacks, :scripts, :url

    def initialize(options = {})
      @options = options
      @callbacks = {}
      @scripts = []
      @shown = false
    end

    def add_action_callback(name, &block)
      @callbacks[name] = block
    end

    def set_url(url)
      @url = url
    end

    def set_on_closed(&block)
      @on_closed = block
    end

    def show
      @shown = true
    end

    def shown?
      @shown
    end

    def close
      @on_closed.call if @on_closed
    end

    def execute_script(script)
      @scripts << script
      nil
    end

    # Stand in for the page: fire one of the callbacks Ruby registered.
    def fire(name, payload = nil)
      callback = @callbacks[name]
      raise "no callback registered for #{name.inspect}" if callback.nil?
      callback.call(nil, payload)
    end
  end
end

# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
module Geom

  # SketchUp stores a transformation as 16 floats in **column-major** order,
  # translation at indices 12-14 -- the OpenGL layout. Getting that backwards
  # transposes every rotation and silently relocates every nested face, so the
  # arithmetic is written out rather than assumed.
  class Transformation
    IDENTITY = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0].freeze

    attr_reader :values

    def initialize(values = nil)
      @values = (values || IDENTITY).map(&:to_f)
    end

    def to_a
      @values.dup
    end

    # Matrix product, self applied after `other` -- the same composition order
    # SketchUp uses for `parent_transform * entity.transformation`.
    def *(other)
      a = @values
      b = other.values
      product = Array.new(16, 0.0)
      4.times do |column|
        4.times do |row|
          sum = 0.0
          4.times { |k| sum += a[k * 4 + row] * b[column * 4 + k] }
          product[column * 4 + row] = sum
        end
      end
      Transformation.new(product)
    end

    def apply(x, y, z)
      a = @values
      w = a[3] * x + a[7] * y + a[11] * z + a[15]
      w = 1.0 if w.zero?
      [(a[0] * x + a[4] * y + a[8] * z + a[12]) / w,
       (a[1] * x + a[5] * y + a[9] * z + a[13]) / w,
       (a[2] * x + a[6] * y + a[10] * z + a[14]) / w]
    end

    def self.scaling(sx, sy = nil, sz = nil)
      sy ||= sx
      sz ||= sx
      new([sx, 0, 0, 0, 0, sy, 0, 0, 0, 0, sz, 0, 0, 0, 0, 1.0])
    end

    def self.translation(dx, dy, dz)
      new([1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, dx, dy, dz, 1.0])
    end
  end

  class Point3d
    attr_reader :x, :y, :z

    def initialize(x, y, z)
      @x = x.to_f
      @y = y.to_f
      @z = z.to_f
    end

    def transform(transformation)
      Point3d.new(*transformation.apply(@x, @y, @z))
    end

    def to_a
      [@x, @y, @z]
    end
  end
end

# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------
module Sketchup

  def self.version
    "22.0.0 (stub)"
  end

  def self.read_default(_section, _key, default = nil)
    default
  end

  def self.write_default(_section, _key, _value)
    true
  end

  # The status bar. Collected rather than discarded so the progress signal is
  # testable — it is the only feedback during a walk that can take 9.7 s.
  def self.status_text=(text)
    @status_text = text
    (@status_history ||= []) << text
  end

  class << self
    attr_reader :status_text, :status_history
  end

  # The frontmost model. Settable here; in SketchUp it follows the frontmost
  # window, which on macOS is why a batch loop over five models can write five
  # files all describing the first one (`CLAUDE.md`).
  def self.active_model
    @active_model ||= Model.new
  end

  class << self
    attr_writer :active_model
  end

  class Layer
    attr_reader :name

    def initialize(name)
      @name = name
    end
  end

  # Real `AttributeDictionary` returns nil for absent keys and is enumerable.
  # Hash already behaves that way, so the only thing worth stubbing is the
  # rule that bites: `attribute_dictionary` returns **nil**, not an empty
  # dictionary, when an entity has none.
  class Entity
    attr_reader :persistent_id, :entityID, :layer

    def initialize(persistent_id:, dictionaries: {}, tag: "Layer0")
      @persistent_id = persistent_id
      @entityID = persistent_id + 100_000
      @dictionaries = dictionaries
      @layer = Layer.new(tag)
    end

    def attribute_dictionary(name)
      @dictionaries[name]
    end
  end

  class Vertex
    attr_reader :position

    def initialize(point)
      @position = point
    end
  end

  class Loop
    attr_reader :vertices

    def initialize(points)
      @vertices = points.map { |p| Vertex.new(Geom::Point3d.new(*p)) }
    end

    def points
      @vertices.map { |v| v.position }
    end
  end

  class Face < Entity
    attr_reader :outer_loop, :loops

    def initialize(points, inner: [], **options)
      super(**options)
      @outer_loop = Loop.new(points)
      @loops = [@outer_loop] + inner.map { |loop| Loop.new(loop) }
    end

    # Newell's method on the transformed boundary. The real API's `area(t)` is
    # the true area under `t`; the local `area` is what a scaled group lies
    # about, so both paths have to be exercised.
    def area(transformation = nil)
      points = @outer_loop.points
      points = points.map { |p| p.transform(transformation) } if transformation
      normal = [0.0, 0.0, 0.0]
      points.each_with_index do |current, index|
        nxt = points[(index + 1) % points.size]
        normal[0] += (current.y - nxt.y) * (current.z + nxt.z)
        normal[1] += (current.z - nxt.z) * (current.x + nxt.x)
        normal[2] += (current.x - nxt.x) * (current.y + nxt.y)
      end
      Math.sqrt(normal[0]**2 + normal[1]**2 + normal[2]**2) / 2.0
    end
  end

  class Edge < Entity
    attr_reader :start, :end

    def initialize(from, to, **options)
      super(**options)
      @start = Vertex.new(Geom::Point3d.new(*from))
      @end = Vertex.new(Geom::Point3d.new(*to))
    end
  end

  class Group < Entity
    attr_reader :entities, :transformation

    def initialize(entities:, transformation: Geom::Transformation.new, **options)
      super(**options)
      @entities = entities
      @transformation = transformation
    end
  end

  class ComponentDefinition
    attr_reader :name, :entities

    def initialize(name, entities = [], dictionaries = {})
      @name = name
      @entities = entities
      @dictionaries = dictionaries
    end

    def attribute_dictionary(key)
      @dictionaries[key]
    end
  end

  class ComponentInstance < Entity
    attr_reader :definition, :transformation
    attr_accessor :name, :glued_to

    def initialize(definition:, transformation: Geom::Transformation.new, name: "",
                   glued_to: nil, **options)
      super(**options)
      @definition = definition
      @transformation = transformation
      @name = name
      @glued_to = glued_to
    end
  end

  class Model
    attr_reader :entities, :title, :path

    def initialize(entities: [], dictionaries: {}, title: "Stub Model", path: "")
      @entities = entities
      @dictionaries = dictionaries
      @title = title
      @path = path
    end

    def attribute_dictionary(name)
      @dictionaries[name]
    end

    def modified?
      false
    end
  end
end
