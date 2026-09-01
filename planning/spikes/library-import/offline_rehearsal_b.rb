# offline_rehearsal_b.rb — run write_library_b.rb's whole write path with NO SketchUp.
#
#   ruby offline_rehearsal_b.rb IN.json OUT.json [probe]
#
# Same stub surface as L-A's offline_rehearsal.rb (see there for the shape); the only
# difference is which module it drives. ⚠ A rehearsal is NOT a capture (house rule).

require "json"

class StubDictionary
  def initialize(hash)
    @hash = hash
  end

  def keys
    @hash.keys
  end
end

class StubModel
  attr_reader :dicts

  def initialize(title, attrs)
    @title = title
    @dicts = { "DesignPH_dict" => attrs.dup }
  end

  def title
    @title
  end

  def path
    "(offline rehearsal — no file)"
  end

  def get_attribute(dict, key)
    (@dicts[dict] || {})[key]
  end

  def set_attribute(dict, key, value)
    (@dicts[dict] ||= {})[key] = value
  end

  def attribute_dictionary(name)
    @dicts.key?(name) ? StubDictionary.new(@dicts[name]) : nil
  end

  def start_operation(_name, _disable_ui)
    true
  end

  def commit_operation
    true
  end

  def abort_operation
    true
  end
end

module Sketchup
  def self.active_model
    @model
  end

  def self.active_model=(model)
    @model = model
  end
end

in_path, out_path = ARGV[0], ARGV[1]
flags = ARGV[2..-1].map(&:to_sym)
abort "usage: ruby offline_rehearsal_b.rb IN.json OUT.json [probe]" unless in_path && out_path

spec = JSON.parse(File.read(in_path))
Sketchup.active_model = StubModel.new(spec.fetch("title"), spec.fetch("attrs"))

require_relative "write_library_b" # prints the dry-run plan on load

DPHLB.write!(*flags)

File.write(out_path, JSON.pretty_generate(
  "title" => Sketchup.active_model.title,
  "dicts" => Sketchup.active_model.dicts
))
puts "rehearsal state -> #{out_path}"
