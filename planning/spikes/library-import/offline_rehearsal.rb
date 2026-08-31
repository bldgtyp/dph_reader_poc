# offline_rehearsal.rb — run write_library.rb's whole write path with NO SketchUp.
#
#   ruby offline_rehearsal.rb IN.json OUT.json [both] [create]
#
# IN.json  — {"title": "...", "attrs": {"designPH_version": "...", "assemblies_calc": "BAh...", ...}}
#            (rehearse.py extracts this from a staged copy's model.dat)
# OUT.json — the same shape after DPHL.write!, for the Python verifier to decode and diff.
#
# ⚠ A rehearsal is NOT a capture (house rule): this proves the script's logic and serialisation
# on the real tables; it says nothing about what designPH will do. Ed's session is not replaced.
#
# The stub implements exactly the Sketchup surface write_library.rb touches. It runs on the
# system Ruby (2.6+); Marshal format 4.8 is identical to SketchUp 2022's Ruby 2.7.

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
abort "usage: ruby offline_rehearsal.rb IN.json OUT.json [both] [create]" unless in_path && out_path

spec = JSON.parse(File.read(in_path))
Sketchup.active_model = StubModel.new(spec.fetch("title"), spec.fetch("attrs"))

revise = flags.delete(:revise)

require_relative "write_library" # prints the dry-run plan on load

DPHL.write!(*flags)
DPHL.revise! if revise

File.write(out_path, JSON.pretty_generate(
  "title" => Sketchup.active_model.title,
  "dicts" => Sketchup.active_model.dicts
))
puts "rehearsal state -> #{out_path}"
